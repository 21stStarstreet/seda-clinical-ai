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

# RAG servisleri (opsiyonel — ChromaDB indexlenmemişse None olabilir)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from rag.retriever import Retriever
    from rag.qa_engine import QAEngine
    from rag.query_preprocessor import QueryPreprocessor

rag_retriever: Optional["Retriever"] = None
rag_qa: Optional["QAEngine"] = None
rag_preprocessor: Optional["QueryPreprocessor"] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıç ve kapanış işlemleri."""
    global predictor, shap_explainer, llm_explainer, audit_logger, access_logger
    global rag_retriever, rag_qa, rag_preprocessor

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

    # RAG servisleri — ChromaDB indexlenmemişse uyarı verir ama çalışmaya devam eder
    try:
        from rag.embedder import Embedder
        from rag.store import VectorStore
        from rag.retriever import Retriever
        from rag.qa_engine import QAEngine
        from rag.query_preprocessor import QueryPreprocessor

        _store = VectorStore()
        if _store.is_empty:
            print("[RAG] ⚠️  ChromaDB henüz indexlenmemiş. "
                  "Kılavuz danışmanı devre dışı. "
                  "Çalıştırın: python -m rag.index_cli")
        else:
            _embedder = Embedder()
            rag_retriever = Retriever(_embedder, _store)
            rag_qa = QAEngine()

            # Kaynak bazlı durum raporu — hangi kılavuzların indekslendiğini göster
            try:
                source_status = _store.indexed_sources()
                status_parts = [f"{src}: {cnt}" for src, cnt in source_status.items()]
                status_str = ", ".join(status_parts)
                missing = [src for src, cnt in source_status.items() if cnt == 0]
                if missing:
                    print(f"[RAG] ✅ Hazır — {_store.chunk_count} chunk ({status_str})")
                    print(f"[RAG] ⚠️  Eksik kaynak(lar): {', '.join(missing)}. "
                          f"Eklemek için: python -m rag.index_cli --source {missing[0]}")
                else:
                    print(f"[RAG] ✅ Hazır — {status_str} (toplam: {_store.chunk_count} chunk)")
            except Exception as src_exc:
                print(f"[RAG] ✅ Hazır — {_store.chunk_count} chunk yüklendi. (Durum detayı alınamadı: {src_exc})")

            # Preprocessor: RAG aktifse başlat (bağımsız try — graceful degradation)
            try:
                rag_preprocessor = QueryPreprocessor(
                    api_key=settings.gemini_api_key,
                )
                print(f"[RAG] ✅ Preprocessor hazır (Two-Stage Query Processing aktif).")
            except Exception as prep_exc:
                print(f"[RAG] ⚠️  Preprocessor başlatılamadı: {prep_exc}. "
                      "Sorgular kısaltma genişletme olmadan işlenecek.")
    except Exception as exc:
        print(f"[RAG] ❌ Başlatılamadı: {exc}. Kılavuz danışmanı devre dışı.")

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
    hekim_notu: Optional[str] = Field(default=None, max_length=1000, description="Hekimin serbest klinik notu")
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
    llm_ozet: str
    llm_fallback_used: bool
    model_versiyonu: str
    islem_suresi_ms: float
    audit_id: int
    kilavuz_atiflar: list[str] = Field(
        default_factory=list,
        description=(
            "Aktif kararlara göre seçilmiş resmi kılavuz atıfları. "
            "Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD) ve "
            "EuroGuiDerm 2025 kaynaklarına dayalı."
        ),
    )


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

    # 3. LLM Açıklaması (2025 Kılavuz Atıflı)
    llm_detayli, llm_ozet, is_fallback, kilavuz_atiflar = llm_explainer.explain(
        prediction,
        shap_explanation,
        hekim_notu=patient_input.hekim_notu,
        # Hasta parametrelerini ilet — kılavuz atıf seçimi için
        pasi=patient_input.pasi_skoru,
        bsa=patient_input.bsa,
        dlqi=patient_input.dlqi,
        vki=patient_input.vki,
        ldl=patient_input.ldl,
        tirnak_tutulumu=patient_input.tirnak_tutulumu,
        sabah_turuklugu=patient_input.sabah_turuklugu_30dk,
        eklem_bulgulari=patient_input.eklem_bulgulari,
        sigara=patient_input.sigara,
    )

    elapsed_ms = (time.time() - start_time) * 1000

    # 4. Audit Log (şifreli)
    audit_id = audit_logger.log(
        patient_dict=patient_input.model_dump(),
        prediction=prediction,
        shap_explanation=shap_explanation,
        llm_text=llm_detayli,
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
        llm_aciklamasi=llm_detayli,
        llm_ozet=llm_ozet,
        llm_fallback_used=is_fallback,
        model_versiyonu=prediction.model_version,
        islem_suresi_ms=round(elapsed_ms, 2),
        audit_id=audit_id,
        kilavuz_atiflar=kilavuz_atiflar,
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


# ─── RAG: Kılavuz Danışmanı ───────────────────────────────────────────────────

class ConversationTurn(BaseModel):
    """Tek bir sohbet turu: hekim sorusu + AI yanıtı."""
    soru: str = Field(..., max_length=500)
    cevap: str = Field(..., max_length=2000)


class GuidelineQueryRequest(BaseModel):
    """Kılavuz danışma isteği."""

    soru: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Hekimin kılavuza yönelttiği serbest metin soru.",
    )
    kaynak_filtre: Optional[list[str]] = Field(
        default=None,
        description="Kısıtlanacak kaynaklar: ['TR2025'] veya ['EG2025'] veya None (her ikisi).",
    )
    gecmis: Optional[list[ConversationTurn]] = Field(
        default=None,
        description=(
            "Son sohbet geçmişi (maks 3 Q/A çifti). "
            "Preprocessor bağlam füzyonu ve QA prompt zenginleştirmesi için kullanılır. "
            "Opsiyonel — None ise stateless davranış (geriye dönük uyumlu)."
        ),
    )


@app.post(
    "/guideline-query",
    summary="Kılavuz Danışmanı — Soru-Cevap",
    tags=["Kılavuz Danışmanı"],
)
@limiter.limit("10/minute")  # Gemini çağrısı pahalı — dakikada 10 yeterli
async def guideline_query(
    request: Request,
    body: GuidelineQueryRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Klinik kılavuzlara (TR2025 + EG2025) serbest metin sorusu yönelt.

    RAG mimarisi:
    1. Soruyu Gemini ile embed et
    2. ChromaDB'den en ilgili 5 kılavuz bölümünü getir
    3. Gemini'ye bağlam + soru gönder, yanıtı kaynaklı al
    4. JSON formatında döndür

    Güvenlik:
    - JWT kimlik doğrulama zorunlu
    - LLM sadece bağlamdaki bilgiden cevap üretir
    - İlaç adı/doz bilgisi yasağı sistem promptunda zorunludur
    """
    import time

    if rag_retriever is None or rag_qa is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Kılavuz danışmanı henüz hazır değil. "
                "Yönetici ile iletişime geçin: python -m rag.index_cli"
            ),
        )

    t0 = time.time()

    # ─── Aşama 1: Sorgu Ön İşleme (Two-Stage RAG — Katman 1) ─────────────────
    # Preprocessor: ham soruyu tıbbi terminolojiye zenginleştir.
    # Preprocessor None ise (başlatılamadıysa) orijinal sorgu kullanılır — graceful degradation.
    sorgu_retrieval = body.soru  # Default: orijinal sorgu
    if rag_preprocessor is not None:
        gecmis_turn_list = (
            [{"soru": t.soru, "cevap": t.cevap} for t in body.gecmis]
            if body.gecmis else []
        )
        try:
            from rag.query_preprocessor import ConversationTurn as PT
            gecmis_turns = (
                [PT(soru=t.soru, cevap=t.cevap) for t in body.gecmis]
                if body.gecmis else []
            )
            prep_result = await rag_preprocessor.preprocess(
                soru=body.soru,
                gecmis=gecmis_turns,
            )
            sorgu_retrieval = prep_result.zengin_sorgu
            if prep_result.onisleme_yapildi:
                import logging as _log
                _log.getLogger(__name__).info(
                    "[guideline-query] Sorgu zenginleştirildi (LLM=%s, %dms): %r → %r",
                    prep_result.llm_kullanildi,
                    prep_result.onisleme_suresi_ms,
                    body.soru,
                    sorgu_retrieval,
                )
        except Exception as prep_exc:
            import logging as _log
            _log.getLogger(__name__).warning(
                "[guideline-query] Preprocessor hatası: %s. Orijinal sorgu kullanılıyor.", prep_exc
            )

    # ─── Aşama 2: Retrieval (zenginleştirilmiş sorguyla) ─────────────────────
    retrieval = rag_retriever.retrieve(
        query=sorgu_retrieval,          # Zengin sorgu → daha iyi ChromaDB eşleşmesi
        source_filter=body.kaynak_filtre,
    )

    retrieval_ms = (time.time() - t0) * 1000

    # ─── Aşama 3: QA (orijinal sorguyla + sohbet geçmişiyle) ─────────────────
    # Kritik tasarım kararı: QA engine'e orijinal sorgu gider.
    # Yanıt hekimin yazdığı soruya uygun tonlanır (zenginleştirilmiş sorgu değil).
    gecmis_dict_list = (
        [{"soru": t.soru, "cevap": t.cevap} for t in body.gecmis]
        if body.gecmis else None
    )
    qa_response = rag_qa.answer(
        soru=body.soru,                 # Orijinal sorgu korunur
        retrieval=retrieval,
        islem_suresi_ms=retrieval_ms,
        gecmis=gecmis_dict_list,        # Sohbet geçmişi → prompt zenginleştirme
    )

    return qa_response.to_dict()
