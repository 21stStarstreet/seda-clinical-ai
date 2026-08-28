"""
API Erişim Log Sistemi
=======================
Her HTTP isteğini kaydeden middleware.

Neden tahmin loglarından ayrı tutuldu?
    - Tahmin logları hasta verisi içerir → şifreli, ayrı tablo
    - Erişim logları sadece: kim, ne zaman, hangi endpoint, HTTP kodu, süre
    - Erişim logları şifrelenmiyor ama hasta verisi içermiyor (sadece kullanıcı adı)

KVKK bağlamı:
    Erişim logları "işlem kayıtları" kapsamındadır.
    Kimin sisteme girdiğini ve hangi işlemleri yaptığını belgelemek zorunludur.

Öğrenme notu — FastAPI Middleware:
    @app.middleware("http") ile tanımlanan fonksiyon her isteği yakalar.
    call_next(request) → asıl endpoint'e devam eder, yanıtı döner.
    Yanıt döndükten sonra loglama yapabiliriz (non-blocking).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import settings

Base = declarative_base()


# ─── ORM: Erişim Log Tablosu ──────────────────────────────────────────────────

class AccessLog(Base):
    """
    Her HTTP isteği için bir satır.

    Kaydedilen bilgiler:
        - timestamp   : ISO 8601 UTC zaman damgası
        - kullanici   : JWT'den çözülen kullanıcı adı (anonim istek → "anonim")
        - yontem      : HTTP metodu (GET, POST, …)
        - endpoint    : İstenen URL yolu (/predict, /audit/logs, …)
        - status_kod  : HTTP yanıt kodu (200, 401, 422, …)
        - sure_ms     : İsteğin toplam işlem süresi (milisaniye)
        - ip_adresi   : İsteği atan IP (rate limiting ile uyumlu)

    Kaydedilmeyen bilgiler (gizlilik):
        - Request body (hasta verileri)
        - Response body
        - Cookie / token değeri
    """

    __tablename__ = "access_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    timestamp   = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    kullanici   = Column(String(50), nullable=False, default="anonim", index=True)
    yontem      = Column(String(10), nullable=False)
    endpoint    = Column(String(200), nullable=False)
    status_kod  = Column(Integer, nullable=False, index=True)
    sure_ms     = Column(Float, nullable=False)
    ip_adresi   = Column(String(50), nullable=True)


# ─── Logger Sınıfı ────────────────────────────────────────────────────────────

class AccessLogger:
    """
    Erişim loglarını SQLite'a kaydeden servis.

    Kullanım (main.py'de):
        access_logger = AccessLogger()

        @app.middleware("http")
        async def http_log_middleware(request, call_next):
            return await access_logger.log_request(request, call_next)
    """

    def __init__(self):
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},  # SQLite çoklu thread desteği
            echo=False,
        )
        # Mevcut audit.db'ye ek tablo oluştur (varsa atla)
        Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)
        print("[AccessLogger] Erişim log tablosu hazır.")

    async def log_request(self, request, call_next):
        """
        FastAPI middleware entry point.
        İsteği işler, süreyi ölçer, kaydeder.
        """
        import time

        # Sağlık kontrolü isteklerini loglama (gereksiz gürültü)
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        baslangic = time.perf_counter()

        # İsteği işle
        response = await call_next(request)

        sure_ms = (time.perf_counter() - baslangic) * 1000

        # Kullanıcıyı JWT'den çek (hata olursa "anonim" yaz)
        kullanici = await self._kullanici_al(request)

        # IP adresini al (proxy arkasındaysa X-Forwarded-For'a bak)
        ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.client.host
            if request.client else "bilinmiyor"
        )

        # Asenkron DB yazımı — response'u bloke etme
        from fastapi.concurrency import run_in_threadpool
        await run_in_threadpool(
            self._kaydet,
            kullanici=kullanici,
            yontem=request.method,
            endpoint=request.url.path,
            status_kod=response.status_code,
            sure_ms=round(sure_ms, 2),
            ip_adresi=ip,
        )

        return response

    async def _kullanici_al(self, request) -> str:
        """
        Authorization header'ından JWT'yi çözerek kullanıcı adını döner.
        Token yoksa veya geçersizse 'anonim' döner.
        """
        try:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return "anonim"
            token = auth_header[7:]

            from jose import jwt as jose_jwt
            payload = jose_jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False},  # Süresi dolmuş token da loglansın
            )
            return payload.get("sub", "anonim")
        except Exception:
            return "anonim"

    def _kaydet(
        self,
        kullanici: str,
        yontem: str,
        endpoint: str,
        status_kod: int,
        sure_ms: float,
        ip_adresi: str,
    ) -> None:
        """Senkron DB yazımı — run_in_threadpool içinde çağrılır (event loop bloke etmez)."""
        session = self._Session()
        try:
            log = AccessLog(
                kullanici=kullanici,
                yontem=yontem,
                endpoint=endpoint,
                status_kod=status_kod,
                sure_ms=sure_ms,
                ip_adresi=ip_adresi,
            )
            session.add(log)
            session.commit()
        except Exception as e:
            session.rollback()  # #10: Transaction güvenliği
            # Log sistemi hiçbir zaman API'nin çökmesine neden olmamalı
            print(f"[AccessLogger] Kayıt hatası (kritik değil): {e}")
        finally:
            session.close()

    # ─── Sorgulama ────────────────────────────────────────────────────────────

    def son_erisimler(self, limit: int = 100) -> list[dict]:
        """Son N erişim kaydını döner (admin paneli için)."""
        session = self._Session()
        try:
            kayitlar = (
                session.query(AccessLog)
                .order_by(AccessLog.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": k.id,
                    "timestamp": k.timestamp.isoformat() if k.timestamp else None,
                    "kullanici": k.kullanici,
                    "yontem": k.yontem,
                    "endpoint": k.endpoint,
                    "status_kod": k.status_kod,
                    "sure_ms": k.sure_ms,
                    "ip_adresi": k.ip_adresi,
                }
                for k in kayitlar
            ]
        finally:
            session.close()

    def kullanici_ozeti(self) -> list[dict]:
        """Kullanıcı başına erişim özeti (son 7 gün)."""
        from datetime import timedelta
        from sqlalchemy import func

        session = self._Session()
        try:
            yedi_gun_once = datetime.now(timezone.utc) - timedelta(days=7)
            ozet = (
                session.query(
                    AccessLog.kullanici,
                    func.count(AccessLog.id).label("toplam_istek"),
                    func.avg(AccessLog.sure_ms).label("ort_sure_ms"),
                    func.max(AccessLog.timestamp).label("son_erisim"),
                )
                .filter(AccessLog.timestamp >= yedi_gun_once)
                .group_by(AccessLog.kullanici)
                .order_by(func.count(AccessLog.id).desc())
                .all()
            )
            return [
                {
                    "kullanici": row.kullanici,
                    "toplam_istek": row.toplam_istek,
                    "ort_sure_ms": round(row.ort_sure_ms or 0, 1),
                    "son_erisim": row.son_erisim.isoformat() if row.son_erisim else None,
                }
                for row in ozet
            ]
        finally:
            session.close()
