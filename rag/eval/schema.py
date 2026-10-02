"""
RAG Değerlendirme Veri Modelleri.
Pydantic tabanlı tip tanımları, metrik sınıfları ve rapor yapıları.
"""

from __future__ import annotations

from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field


# ─── Altın Set Modelleri ──────────────────────────────────────────────────────

QuestionType = Literal[
    "dogrudan",               # Tek sayfadan doğrudan bilgi
    "sentez",                 # Birden fazla sayfa / bölüm sentezi
    "tr_eg_karsilastirma",    # TR2025 vs EG2025 karşılaştırması
    "kisaltma_ve_diyalog",    # Tıbbi kısaltmalar (MTX, Anti-TNF) ve konuşma dili
    "kapsam_disi",            # Kılavuz dışı soru (bulunamadi: true beklenir)
    "yanlis_oncul",           # Hatalı klinik öncül içeren soru
]


class ExpectedSource(BaseModel):
    """Bir soru için kabul edilebilir kılavuz kaynağı ve sayfa aralığı."""
    source_code: Literal["TR2025", "EG2025"]
    sayfalar: List[int] = Field(
        description="Bu bilginin yer aldığı kabul edilebilir sayfa numaraları."
    )


class GoldenQuestion(BaseModel):
    """Altın değerlendirme setindeki tek bir soru kaydı."""
    id: str = Field(description="Tekil soru ID'si (Örn: Q01)")
    soru: str = Field(description="Değerlendirme sorusu")
    tur: QuestionType = Field(description="Soru kategorisi")
    kapsam_ici: bool = Field(
        default=True,
        description="True ise ilgili bilgi kılavuzda mevcut; False ise kapsam dışı / çekimser kalınmalı."
    )
    beklenen_kaynaklar: List[ExpectedSource] = Field(
        default_factory=list,
        description="Doğru kabul edilecek kaynak ve sayfa eşleşmeleri."
    )
    kilit_noktalar: List[str] = Field(
        default_factory=list,
        description="Cevabın içermesi gereken klinik kilit kavramlar/ifadeler."
    )
    sayisal_degerler: List[str] = Field(
        default_factory=list,
        description="Cevapta doğrulanması gereken eşik, doz veya yüzdeler (Örn: '10', '15 mg')."
    )
    aciklama: Optional[str] = Field(
        default=None,
        description="Hekim/Uzman notu veya klinik bağlam."
    )


# ─── Retrieval Metrik Modelleri ───────────────────────────────────────────────

class RetrievedChunkInfo(BaseModel):
    source_code: str
    doc_page: int
    heading: str
    distance: float
    text_snippet: str
    is_expected: bool


class RetrievalResultItem(BaseModel):
    question_id: str
    soru: str
    tur: str
    kapsam_ici: bool
    min_distance: float
    retrieved_hits: List[RetrievedChunkInfo]
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float
    passed_threshold: bool  # min_distance <= threshold


class ThresholdSweepPoint(BaseModel):
    threshold: float
    precision: float
    recall: float
    f1: float
    accuracy: float
    tp: int
    fp: int
    tn: int
    fn: int


class RetrievalSummary(BaseModel):
    total_questions: int
    kapsam_ici_count: int
    kapsam_disi_count: int
    
    # Sıralama ve Getirme Başarımı (Kapsam İçi Sorular İçin)
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float

    # Kaynak Bazlı Ayrımlar
    tr2025_recall_at_5: float
    eg2025_recall_at_5: float
    cross_lingual_recall_at_5: float  # Türkçe soru → İngilizce kılavuz getirme başarımı

    # Kategori Bazlı Recall@5
    kategori_bazli_recall: Dict[str, float]

    # Eşik Değerlendirmesi
    current_threshold: float
    current_threshold_f1: float
    optimal_threshold: float
    optimal_threshold_f1: float
    sweep_curve: List[ThresholdSweepPoint] = Field(default_factory=list)


# ─── Generation Metrik Modelleri ──────────────────────────────────────────────

class CitationVerificationItem(BaseModel):
    kaynak_kodu: str
    sayfa: int
    in_retrieved_context: bool


class QuoteVerificationItem(BaseModel):
    alinti: str
    kaynak_kodu: str
    sayfa: int
    is_exact_match: bool
    is_fuzzy_match: bool


class GenerationResultItem(BaseModel):
    question_id: str
    soru: str
    tur: str
    kapsam_ici: bool
    bulunamadi: bool
    dogru_cekimserlik: Optional[bool]
    cevap_metni: Optional[str]
    
    # Atıf doğruluğu (sayfa gerçekten getirilen bağlamda var mı?)
    citations: List[CitationVerificationItem]
    citation_precision: float
    
    # Alıntı doğruluğu (alıntılanan cümle chunk metninde geçiyor mu?)
    quotes: List[QuoteVerificationItem]
    quote_veracity: float

    # Kilit nokta ve sayısal doğruluk
    kilit_nokta_kapsama: float
    sayisal_dogruluk: float
    eksik_kilit_noktalar: List[str]
    eksik_sayisal_degerler: List[str]
    
    islem_suresi_ms: float
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    oncul_durum: Optional[str] = None
    hatalar: List[str] = Field(default_factory=list)


class GenerationSummary(BaseModel):
    total_evaluated: int
    proper_refusal_rate: float       # Kapsam dışı sorularda doğru bulunamadi oranı
    mean_citation_precision: float   # Üretilen sayfa atıflarının bağlamda bulunma oranı
    mean_quote_veracity: float       # Alıntıların chunk içinde harfi harfine bulunma oranı
    mean_keypoint_coverage: float    # Kilit noktaların cevapta yer alma oranı
    mean_numerical_accuracy: float   # Sayısal değerlerin doğru aktarılma oranı
    avg_latency_ms: float
    fallback_count: int = 0
    fallback_questions: List[Dict] = Field(default_factory=list)
    yanlis_oncul_stats: Dict[str, int] = Field(default_factory=dict)


# ─── Tam Değerlendirme Raporu ─────────────────────────────────────────────────

class EvalReport(BaseModel):
    golden_set_path: str = "rag/eval/golden_set.json"
    golden_set_mtime: str = ""
    timestamp: str
    model_version: str
    embedding_model: str
    retrieval: RetrievalSummary
    generation: Optional[GenerationSummary] = None
    itemized_retrieval: List[RetrievalResultItem] = Field(default_factory=list)
    itemized_generation: List[GenerationResultItem] = Field(default_factory=list)
