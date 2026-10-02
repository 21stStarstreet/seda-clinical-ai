"""
Audit Log Sistemi (Faz 4: KVKK Uyumlu Şifreleme Eklendi)
==========================================================
Her tahmin: girdi + çıktı + SHAP + LLM açıklama + timestamp.
SQLAlchemy ORM ile SQLite (geliştirme) / PostgreSQL (üretim).

Faz 4 değişikliği:
    Hassas klinik alanlar (input_json, shap_json, llm_explanation)
    Fernet/AES-128 ile şifrelenerek kaydedilir.
    Disk üzerinde açık metin hasta verisi bulunmaz → KVKK uyumlu.

Öğrenme notu — Fernet şifreleme:
    Fernet simetrik şifrelemedir (AES-128-CBC + HMAC-SHA256).
    Tek bir anahtar hem şifreler hem çözer.
    Anahtar .env dosyasında saklanır, kaynak koda girmez.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
import functools

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, Float
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import settings

log = logging.getLogger(__name__)

Base = declarative_base()


# ─── Şifreleme Yardımcısı ─────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    """
    Settings'ten şifreleme anahtarını okur ve Fernet nesnesi döner.
    Performans için lru_cache ile önbelleğe alınmıştır.
    """
    key = settings.encryption_key
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_field(value: str) -> str:
    """Metni Fernet ile şifrele, base64 string döndür."""
    if not value:
        return value
    cipher = _get_cipher()
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_field(value: str) -> str:
    """Fernet şifrelenmiş metni çöz."""
    if not value:
        return value
    try:
        cipher = _get_cipher()
        return cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception as e:
        # Eski (şifrelenmemiş) kayıtlar veya anahtar uyumsuzluğu için geri dönüş
        log.warning("[Audit] decrypt_field başarısız (ham değer döndürüldü): %s", e)
        return value


# ─── TC Hash Yardımcısı ───────────────────────────────────────────────────────

def hash_tc(tc_no: str) -> str:
    """TC Kimlik No'nun SHA-256 hash'ini üret (geri döndürülemez, sadece arama için)."""
    return hashlib.sha256(tc_no.strip().encode("utf-8")).hexdigest()


# ─── Hasta Kimlik Tablosu (Legacy - Supabase/PostgreSQL'e kaydedilmez) ─────────
LegacyPatientBase = declarative_base()

class Patient(LegacyPatientBase):
    """
    Hasta kimlik bilgileri tablosu (Legacy yerel model).
    Zero-PII mimarisi gereği bu tablo PostgreSQL/Supabase bulutuna ASLA kaydedilmez.
    """

    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tc_hash = Column(String(64), nullable=False, unique=True, index=True)
    tc_encrypted        = Column(Text, nullable=False)
    ad_soyad            = Column(Text, nullable=False)
    dogum_tarihi        = Column(Text, nullable=True)
    cinsiyet            = Column(String(20), nullable=True)
    telefon             = Column(Text, nullable=True)
    kan_grubu           = Column(String(10), nullable=True)
    ilk_tani_tarihi     = Column(Date, nullable=True)
    hekim_notu          = Column(Text, nullable=True)
    kayit_tarihi = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# ─── ORM Modeli (Sadece Anonim Tahmin ve Klinik Loglar) ─────────────────────────

class PredictionLog(Base):
    """
    Audit log tablosu — her satır bir tahmin kaydıdır.
    Zero-PII: TC, ad, soyad, cinsiyet, doğum tarihi vb. kişisel veri ASLA içermez.
    """

    __tablename__ = "prediction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    hasta_id = Column(String(50), nullable=True, index=True)
    model_version = Column(String(20), nullable=False)

    # Girdi — ŞİFRELİ (Fernet) - Yalnızca anonim klinik özellikler
    input_json = Column(Text, nullable=False)

    # ML Çıktısı — açık (zaten anonim binary değerler)
    pred_ftr = Column(Integer, nullable=False)
    pred_aile_hekimligi = Column(Integer, nullable=False)
    pred_sistemik_tedavi = Column(Integer, nullable=False)
    prob_ftr = Column(Float, nullable=False)
    prob_aile_hekimligi = Column(Float, nullable=False)
    prob_sistemik_tedavi = Column(Float, nullable=False)

    # SHAP — ŞİFRELİ (Fernet)
    shap_json = Column(Text, nullable=True)

    # LLM açıklama — ŞİFRELİ (Fernet)
    llm_explanation = Column(Text, nullable=True)

    # LLM fallback kullanıldı mı? — açık
    llm_fallback_used = Column(Integer, nullable=False, default=0)

    # İşlem süresi (ms) — açık
    processing_time_ms = Column(Float, nullable=True)


# ─── Audit Logger Servisi ─────────────────────────────────────────────────────

class AuditLogger:
    """Tahmin loglarını şifreleyerek veritabanına kaydeden servis."""

    def __init__(self, database_url: str = ""):
        url = database_url or settings.database_url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, echo=False, connect_args=connect_args)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        print(f"[Audit] Veritabanı hazır (şifreli): {url}")

    def log(
        self,
        patient_dict: dict,
        prediction,
        shap_explanation: dict,
        llm_text: str,
        llm_fallback_used: bool = False,
        processing_time_ms: float = 0.0,
        patient_tc_hash: Optional[str] = None,
    ) -> int:
        """
        Tahmin kaydını şifreleyerek veritabanına yaz.
        Zero-PII: Kimlik ve demografik veriler (TC, ad, soyad, doğum tarihi,
        cinsiyet, ilk tanı tarihi, telefon) veritabanına KESİNLİKLE kaydedilmez.
        Sadece anonim klinik özellikler saklanır.
        """
        EXCLUDED_PII = {
            "extra_features", "patient_tc_hash", "tc_no", "tc", "hasta_adi", 
            "ad_soyad", "dogum_tarihi", "cinsiyet", "ilk_tani_tarihi", "telefon", "hekim_notu"
        }
        sanitized_input = {k: v for k, v in patient_dict.items() if k not in EXCLUDED_PII}
        raw_input = json.dumps(sanitized_input, ensure_ascii=False)
        raw_shap = json.dumps(shap_explanation, ensure_ascii=False)

        with self.SessionLocal() as session:
            record = PredictionLog(
                hasta_id=patient_dict.get("hasta_id"),
                model_version=prediction.model_version,
                # ── Hassas alanlar şifreli ──
                input_json=encrypt_field(raw_input),
                shap_json=encrypt_field(raw_shap),
                llm_explanation=encrypt_field(llm_text),
                # ── Binary tahminler açık ──
                pred_ftr=int(prediction.labels.ftr),
                pred_aile_hekimligi=int(prediction.labels.aile_hekimligi),
                pred_sistemik_tedavi=int(prediction.labels.sistemik_tedavi),
                prob_ftr=prediction.probabilities["ftr"],
                prob_aile_hekimligi=prediction.probabilities["aile_hekimligi"],
                prob_sistemik_tedavi=prediction.probabilities["sistemik_tedavi"],
                llm_fallback_used=int(llm_fallback_used),
                processing_time_ms=processing_time_ms,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id

    def get_logs(self, limit: int = 100, hasta_id: Optional[str] = None) -> list[dict]:
        """
        Audit loglarını sorgula ve hassas alanları çöz.
        Bu metod yalnızca admin yetkisiyle çağrılmalıdır (API katmanında kontrol edilir).
        """
        with self.SessionLocal() as session:
            query = session.query(PredictionLog).order_by(
                PredictionLog.timestamp.desc()
            )
            if hasta_id:
                query = query.filter(PredictionLog.hasta_id == hasta_id)
            records = query.limit(limit).all()

        result = []
        for r in records:
            input_json_str = decrypt_field(r.input_json) if r.input_json else None
            result.append({
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "hasta_id": r.hasta_id,
                "hasta_adi": None,
                "model_version": r.model_version,
                "tahmin": {
                    "ftr": bool(r.pred_ftr),
                    "aile_hekimligi": bool(r.pred_aile_hekimligi),
                    "sistemik_tedavi": bool(r.pred_sistemik_tedavi),
                },
                "processing_time_ms": r.processing_time_ms,
                "input_json": input_json_str,
                "patient_tc_hash": None,
            })
            
        return result

    def get_logs_by_tc_hash(self, tc_hash: str, limit: int = 50) -> list[dict]:
        """Zero-PII mimarisi gereği TC bazlı log tutulmaz."""
        return []


    def get_log_by_id(self, log_id: int) -> dict | None:
        """
        Spesifik bir log kaydını id ile getirir.
        Girdi parametreleri (input_json), SHAP açıklamaları (shap_json) ve LLM (llm_explanation)
        alanlarını Fernet şifresinden çözerek tam detaylı dict döner.
        """
        with self.SessionLocal() as session:
            r = session.query(PredictionLog).filter(PredictionLog.id == log_id).first()
            if not r:
                return None

            try:
                patient_input = json.loads(decrypt_field(r.input_json)) if r.input_json else {}
                if "yas" in patient_input and isinstance(patient_input["yas"], float):
                    patient_input["yas"] = int(patient_input["yas"])
            except Exception as e:
                log.warning("[Audit] get_log_by_id patient_input JSON çözme hatası (id=%s): %s", log_id, e)
                patient_input = {}
                
            try:
                shap_aciklamalari = json.loads(decrypt_field(r.shap_json)) if r.shap_json else {}
            except Exception as e:
                log.warning("[Audit] get_log_by_id shap_json çözme hatası (id=%s): %s", log_id, e)
                shap_aciklamalari = {}
                
            llm_aciklamasi = decrypt_field(r.llm_explanation) if r.llm_explanation else ""

            aktif_birimler = []
            if r.pred_ftr: aktif_birimler.append("Fizik Tedavi ve Rehabilitasyon (FTR)")
            if r.pred_aile_hekimligi: aktif_birimler.append("Aile Hekimliği")
            if r.pred_sistemik_tedavi: aktif_birimler.append("Sistemik Tedavi")

            prediction_response = {
                "hasta_id": r.hasta_id,
                "tahmin": {
                    "ftr": {
                        "karar": bool(r.pred_ftr),
                        "olasilik": r.prob_ftr,
                        "goruntu_adi": "Fizik Tedavi ve Rehabilitasyon (FTR)"
                    },
                    "aile_hekimligi": {
                        "karar": bool(r.pred_aile_hekimligi),
                        "olasilik": r.prob_aile_hekimligi,
                        "goruntu_adi": "Aile Hekimliği"
                    },
                    "sistemik_tedavi": {
                        "karar": bool(r.pred_sistemik_tedavi),
                        "olasilik": r.prob_sistemik_tedavi,
                        "goruntu_adi": "Sistemik Tedavi"
                    }
                },
                "aktif_birimler": aktif_birimler,
                "shap_aciklamalari": shap_aciklamalari,
                "llm_aciklamasi": llm_aciklamasi,
                "llm_fallback_used": bool(r.llm_fallback_used),
                "model_versiyonu": r.model_version,
                "islem_suresi_ms": r.processing_time_ms or 0.0,
                "audit_id": r.id
            }

            return {
                "patient_input": patient_input,
                "prediction_response": prediction_response
            }
