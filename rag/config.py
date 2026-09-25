"""
RAG sistem sabitleri.
Tüm ayarlar buradan yönetilir — sihirli sayılar koda gömülmez.
"""

from __future__ import annotations

from pathlib import Path

# ─── Proje Kök Dizini ─────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent

# ─── PDF Kaynakları ───────────────────────────────────────────────────────────
SOURCES: dict[str, dict] = {
    "TR2025": {
        "path": PROJECT_ROOT / "docs" / "guidelines" / "psoriasiskitap2025_SONrenkli.pdf",
        "display_name": "Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD)",
        "short_name": "TR2025",
        "language": "tr",
        "url": "www.psokid.org",
    },
    "EG2025": {
        "path": PROJECT_ROOT / "docs" / "guidelines" / "Guidelinelar.pdf",
        "display_name": "EuroGuiDerm — Systemic Treatment of Psoriasis Vulgaris (2025)",
        "short_name": "EG2025",
        "language": "en",
        "url": "doi.org/10.1111/jdv.16752",
        "max_pages": 234,  # Guidelinelar.pdf içinde s.235 sonrası mükerrer TR2025, Atopik Egzama ve Ürtiker'dir
    },
}

# ─── ChromaDB ────────────────────────────────────────────────────────────────
CHROMA_DB_PATH = str(PROJECT_ROOT / "rag" / "chroma_db")
COLLECTION_NAME = "seda_guidelines"

# ─── Chunking ────────────────────────────────────────────────────────────────
# 400 token ≈ 300 kelime — 5 chunk = ~2.000 token bağlam, yönetilebilir
CHUNK_SIZE_WORDS = 280
CHUNK_OVERLAP_WORDS = 40
MIN_CHUNK_WORDS = 25        # Bu eşiğin altındaki chunk'lar atlanır

# ─── Embedding ───────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_BATCH_SIZE = 15   # 15 chunk ≈ 4000 token — TPM ve RPM sınırları için en güvenli bütçe
EMBEDDING_DELAY_SEC = 3.5   # Rate limit koruması: istekler arası 3.5s bekleme (17 RPM altında kalır)
TASK_TYPE_INDEX = "RETRIEVAL_DOCUMENT"
TASK_TYPE_QUERY = "RETRIEVAL_QUERY"

# ─── Retrieval ───────────────────────────────────────────────────────────────
TOP_K = 5
# ChromaDB cosine distance: 0 = aynı, 2 = zıt
# 0.65 üzeri → ilgisiz soru → "Bulunamadı" yanıtı
# Not: 0.75'ten 0.65'e düşürüldü — önceki değer çok geniş eşik sağlıyordu;
# FTR sorguları için biyolojik ajan/topikal tedavi sayfaları yanlış olarak eşleşiyordu.
MAX_DISTANCE_THRESHOLD = 0.65

# ─── Generation ──────────────────────────────────────────────────────────────
# Birincil model: gemini-3.1-flash-lite-preview — Yüksek kota kapasitesi, hızlı yanıt (~3s).
# Yedek zinciri: gemini-3.1-flash-lite, gemini-3-flash-preview, gemini-3.5-flash-lite
QA_MODEL = "gemini-3.1-flash-lite-preview"

# Fallback zinciri: Birincil model 429/503/timeout verirse sıradaki denenir.
QA_MODEL_FALLBACKS: list[str] = [
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
]

QA_TEMPERATURE = 0.1        # Klinik doğruluk ve akıcı sentez
QA_MAX_OUTPUT_TOKENS = 3500 # Kapsamlı klinik açıklamalar ve kaynak alıntıları için tam bütçe
QA_TIMEOUT_SEC = 12.0       # Model başına sert zaman aşımı (asla frontend'i 90s bekletmez)

# ─── Query Preprocessor ──────────────────────────────────────────────────────
# Sorgu ön işleme için hafif model: ~80ms gecikme, düşük kota tüketimi.
PREPROCESSOR_MODEL = "models/gemini-3.1-flash-lite-preview"
PREPROCESSOR_MAX_TOKENS = 150  # Reformüle edilmiş sorgu için 2 cümle yeterli
PREPROCESSOR_TIMEOUT_SEC = 4.0 # Ön işleme için sert zaman aşımı