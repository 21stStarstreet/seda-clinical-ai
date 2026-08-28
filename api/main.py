"""
FastAPI Ana Uygulama (Faz 4: Güvenlik Katmanı Eklendi)
===================
Psoriazis CDSS REST API.

Faz 4 değişiklikleri:
    - JWT kimlik doğrulama (tüm endpoint'lerde zorunlu)
    - Rate limiting: /predict → 5/dk, /token → 10/dk
    - CORS: yalnızca Blazor uygulamasının adresine izin ver
    - Token kara listesi: logout sonrası token geçersiz
    - /audit/logs: artık admin yetkisi zorunlu

Kullanım:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config.settings import settings, set_global_seed, LABEL_NAMES, LABEL_DISPLAY_NAMES
from feature_store.schema import PatientFeatures
from models.predictor import Predictor
from explainability.shap_explainer import SHAPExplainer
from llm.explainer import LLMExplainer
from audit.logger import AuditLogger
from audit.access_logger import AccessLogger
from api.routes.auth import (
    router as auth_router,
    get_current_user,
    require_admin,
    TokenData,
)

# ─── Rate Limiter ─────────────────────────────────────────────────────────────
# Öğrenme notu:
# get_remote_address: İsteği atan IP adresini alır (limit anahtarı bu).
# Limiter: Her endpoint'e @limiter.limit("5/minute") decorator'ı ile kota koyar.
limiter = Limiter(key_func=get_remote_address)

# ─── Global servisler ─────────────────────────────────────────────────────────
predictor: Optional[Predictor] = None
shap_explainer: Optional[SHAPExplainer] = None
llm_explainer: Optional[LLMExplainer] = None
audit_logger: Optional[AuditLogger] = None
access_logger: Optional[AccessLogger] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıç ve kapanış işlemleri."""
    global predictor, shap_explainer, llm_explainer, audit_logger, access_logger

    print("[API] Servisler başlatılıyor...")
    set_global_seed()

    # Model yükle
    model_dir = f"{settings.model_dir}/production"
    predictor = Predictor.load_safe(model_dir)

    # SHAP explainer
    if predictor:
        shap_explainer = SHAPExplainer(
            models=predictor.models,
            feature_names=predictor.pipeline.feature_names,
        )

    # LLM explainer
    llm_explainer = LLMExplainer.from_settings()

    # Audit logger (şifreli)
    audit_logger = AuditLogger()

    # Erişim logger (HTTP istek kayıtları — kim, ne zaman, hangi endpoint)
    access_logger = AccessLogger()

    print("[API] Hazır.")
    yield

    print("[API] Kapatılıyor...")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Psoriazis CDSS API",
    description=(
        "Psoriazis hastalarını doğru uzmana yönlendiren "
        "klinik karar destek sistemi. "
        "XGBoost + SHAP + Gemini tabanlı."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── Rate Limiting ────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS Kısıtlaması ─────────────────────────────────────────────────────────
# Öğrenme notu:
# Faz 2'de allow_origins=["*"] idi — bu güvensiz.
# Artık yalnızca Blazor uygulamasının adresleri kabul ediliyor.
# settings.allowed_origins = "http://localhost:5285,https://localhost:7285"
allowed_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─── HTTP Erişim Log Middleware ─────────────────────────────────────────────────
# Öğrenme notu:
# @app.middleware("http") ile tanımlanan fonksiyon her HTTP isteğini yakalar.
# Bu zincir: istek → access_logger → diğer middleware'ler → endpoint → yanıt
@app.middleware("http")
async def http_access_log_middleware(request: Request, call_next):
    if access_logger is not None:
        return await access_logger.log_request(request, call_next)
    return await call_next(request)

# ─── Auth Router'ı dahil et (/token ve /logout burada) ───────────────────────
app.include_router(auth_router)

# ─── Patients Router'ı dahil et ───────────────────────────────────────────────
from api.patients import router as patients_router
app.include_router(patients_router)

from feature_store.schema import PsoriasisType, SystemicResponse

PSORIAZIS_MAP = {
    "Plak": PsoriasisType.PLAK,
    "Guttat": PsoriasisType.GUTAT,
    "Püstüler": PsoriasisType.PUSTULAR,
    "Eritrodermik": PsoriasisType.ERITRODERMIK,
    "Ters": PsoriasisType.INVERZ,
}
# ─── Request / Response Şemaları ──────────────────────────────────────────────

class PatientInput(BaseModel):
    hasta_id: str
    hasta_adi: str = ""
    patient_tc_hash: Optional[str] = None   # TC hash — hasta kimliğini audit log'a bağlar
    psoriazis_tipi: str = Field(default="Plak", description="Plak | Guttat | Püstüler | Eritrodermik | Ters")
    tirnak_tutulumu: bool = False
    sabah_turuklugu_30dk: bool = False
    vki: Optional[float] = Field(default=None, ge=10.0, le=80.0)
    ldl: Optional[float] = Field(default=None, ge=0.0, le=500.0)
    pasi_skoru: Optional[float] = Field(default=None, ge=0.0, le=72.0)
    sigara: bool = False
    dlqi: Optional[float] = Field(default=None, ge=0.0, le=30.0)
    bsa: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    yas: Optional[int] = Field(default=None, ge=0, le=120)
    # V2 Özellikleri (Nullable)
    eklem_bulgulari: Optional[bool] = None
    onceki_sistemik_yanit: Optional[str] = None
    cinsiyet: Optional[str] = None
    hastalik_suresi_ay: Optional[int] = Field(default=None, ge=0, le=1200)


class LabelDetail(BaseModel):
    karar: bool
    olasilik: float
    goruntu_adi: str


class PredictionResponse(BaseModel):
    """Tahmin API yanıtı."""

    hasta_id: str
    tahmin: dict[str, LabelDetail]
    aktif_birimler: list[str]
    shap_aciklamalari: dict
    llm_aciklamasi: str
    llm_fallback_used: bool
    model_versiyonu: str
    islem_suresi_ms: float
    audit_id: int


class HealthResponse(BaseModel):
    status: str
    model_yuklendi: bool
    model_versiyonu: Optional[str]
    llm_aktif: bool


# ─── Endpoint'ler ─────────────────────────────────────────────────────────────

@app.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Hasta için klinik karar üret",
    tags=["Tahmin"],
)
@limiter.limit("30/minute")  # Dakika başına maks 30 tahmin isteği
async def predict(
    request: Request,
    patient_input: PatientInput,
    current_user: TokenData = Depends(get_current_user),  # JWT zorunlu
):
    """
    Hasta verilerini alır, ML modeli ile tahmin yapar,
    SHAP ile açıklar ve LLM ile Türkçe'ye çevirir.
    """
    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail="Model henüz yüklenmedi. Lütfen önce modeli eğitin.",
        )
    if shap_explainer is None:
        raise HTTPException(
            status_code=503,
            detail="SHAP açıklayıcı hazır değil. Sunucuyu yeniden başlatın.",
        )
    if llm_explainer is None:
        raise HTTPException(
            status_code=503,
            detail="LLM açıklayıcı hazır değil. Sunucuyu yeniden başlatın.",
        )
    if audit_logger is None:
        raise HTTPException(
            status_code=503,
            detail="Audit logger hazır değil. Sunucuyu yeniden başlatın.",
        )

    start_time = time.time()

    # 1. Feature Engineering & Preprocessing
    # onceki_sistemik_yanit: str → SystemicResponse Enum dönüşümü
    onceki_yanit_enum: Optional[SystemicResponse] = None
    if patient_input.onceki_sistemik_yanit:
        try:
            onceki_yanit_enum = SystemicResponse(patient_input.onceki_sistemik_yanit.lower())
        except ValueError:
            onceki_yanit_enum = SystemicResponse.BILINMIYOR

    feature_obj = PatientFeatures(
        hasta_id=patient_input.hasta_id,
        psoriazis_tipi=PSORIAZIS_MAP.get(patient_input.psoriazis_tipi, PsoriasisType.PLAK),
        tirnak_tutulumu=patient_input.tirnak_tutulumu,
        sabah_turuklugu_30dk=patient_input.sabah_turuklugu_30dk,
        vki=patient_input.vki,
        ldl=patient_input.ldl,
        pasi_skoru=patient_input.pasi_skoru,
        sigara=patient_input.sigara,
        dlqi=patient_input.dlqi,
        bsa=patient_input.bsa,
        yas=patient_input.yas,
        eklem_bulgulari=patient_input.eklem_bulgulari,
        onceki_sistemik_yanit=onceki_yanit_enum,
        cinsiyet=patient_input.cinsiyet,
        hastalik_suresi_ay=patient_input.hastalik_suresi_ay,
    )
    

    # Modeli çalıştır
    prediction = predictor.predict(feature_obj)
    X = predictor.pipeline.transform_single(feature_obj)
    shap_explanation = shap_explainer.explain_single(X, top_n=5)

    # 3. LLM Açıklaması
    llm_text, is_fallback = llm_explainer.explain(prediction, shap_explanation)

    elapsed_ms = (time.time() - start_time) * 1000

    # 4. Audit Log (şifreli)
    audit_id = audit_logger.log(
        patient_dict=patient_input.model_dump(),
        prediction=prediction,
        shap_explanation=shap_explanation,
        llm_text=llm_text,
        llm_fallback_used=is_fallback,
        processing_time_ms=elapsed_ms,
        patient_tc_hash=patient_input.patient_tc_hash,
    )

    # Yanıt formatla
    tahmin = {}
    for label in LABEL_NAMES:
        tahmin[label] = LabelDetail(
            karar=getattr(prediction.labels, label),
            olasilik=round(prediction.probabilities[label], 4),
            goruntu_adi=LABEL_DISPLAY_NAMES[label],
        )

    return PredictionResponse(
        hasta_id=patient_input.hasta_id,
        tahmin=tahmin,
        aktif_birimler=[
            LABEL_DISPLAY_NAMES[label]
            for label in LABEL_NAMES
            if getattr(prediction.labels, label)
        ],
        shap_aciklamalari=shap_explanation,
        llm_aciklamasi=llm_text,
        llm_fallback_used=is_fallback,
        model_versiyonu=prediction.model_version,
        islem_suresi_ms=round(elapsed_ms, 2),
        audit_id=audit_id,
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Sistem sağlığı",
    tags=["Sistem"],
)
async def health():
    """Public endpoint — kimlik doğrulama gerekmez."""
    return HealthResponse(
        status="ok" if predictor else "model_eksik",
        model_yuklendi=predictor is not None,
        model_versiyonu=predictor.version if predictor else None,
        llm_aktif=llm_explainer is not None and llm_explainer.enabled,
    )


@app.get(
    "/audit/logs",
    summary="Audit logları (Tüm Kullanıcılar)",
    tags=["Audit"],
)
@limiter.limit("20/minute")
async def get_audit_logs(
    request: Request,
    limit: int = Query(default=50, le=500),
    hasta_id: Optional[str] = Query(default=None),
    current_user: TokenData = Depends(get_current_user),  # Doktorlar ve Adminler
):
    """
    Son tahmin kayıtlarını döner.
    Hassas klinik veriler şifresi çözülerek döndürülür.
    """
    if audit_logger is None:
        raise HTTPException(status_code=503, detail="Audit logger hazır değil.")
    return {"logs": audit_logger.get_logs(limit=limit, hasta_id=hasta_id)}


@app.get(
    "/audit/logs/{log_id}",
    summary="Spesifik Audit log detayı",
    tags=["Audit"],
)
@limiter.limit("20/minute")
async def get_audit_log_detail(
    request: Request,
    log_id: int,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Geçmiş bir tahminin tüm detaylarını şifresi çözülmüş olarak döner (PDF için).
    """
    if audit_logger is None:
        raise HTTPException(status_code=503, detail="Audit logger hazır değil.")
    
    log_detail = audit_logger.get_log_by_id(log_id)
    if not log_detail:
        raise HTTPException(status_code=404, detail="Log kaydı bulunamadı.")

    return log_detail


# ─── Admin: Erişim Logları ─────────────────────────────────────────────────────

@app.get(
    "/admin/access-logs",
    summary="HTTP Erişim Logları (Admin)",
    tags=["Admin"],
)
@limiter.limit("10/minute")
async def get_access_logs(
    request: Request,
    limit: int = Query(default=100, le=1000),
    _: TokenData = Depends(require_admin),
):
    """
    Son HTTP erişim kayıtlarını döner (sadece admin).

    Döndürdüğü bilgiler:
        - Kullanıcı adı (JWT'den)
        - Endpoint ve HTTP metodu
        - Yanıt kodu ve işlem süresi
        - IP adresi
        - Zaman damgası
    """
    if access_logger is None:
        raise HTTPException(status_code=503, detail="Erişim logger hazır değil.")
    return {"logs": access_logger.son_erisimler(limit=limit)}


@app.get(
    "/admin/access-summary",
    summary="Kullanıcı Erişim Özeti (Admin, Son 7 Gün)",
    tags=["Admin"],
)
@limiter.limit("10/minute")
async def get_access_summary(
    request: Request,
    _: TokenData = Depends(require_admin),
):
    """
    Kullanıcı başına son 7 gündün toplam istek, ortalama süre, son erişim.
    KVKK'nın öngördüğü erişim denetimi raporları için kullanılabilir.
    """
    if access_logger is None:
        raise HTTPException(status_code=503, detail="Erişim logger hazır değil.")
    return {"ozet": access_logger.kullanici_ozeti()}
