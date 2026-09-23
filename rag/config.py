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
EMBEDDING_BATCH_SIZE = 10   # Free tier TPM güvenliği için küçük batch
EMBEDDING_DELAY_SEC = 2.0   # Rate limit koruması: batch aralarında 2s
TASK_TYPE_INDEX = "RETRIEVAL_DOCUMENT"
TASK_TYPE_QUERY = "RETRIEVAL_QUERY"

# ─── Retrieval ───────────────────────────────────────────────────────────────
TOP_K = 5
# ChromaDB cosine distance: 0 = aynı, 2 = zıt
# 0.75 üzeri → ilgisiz soru → "Bulunamadı" yanıtı
MAX_DISTANCE_THRESHOLD = 0.75

# ─── Generation ──────────────────────────────────────────────────────────────
QA_MODEL = "gemini-3.6-flash"
QA_TEMPERATURE = 0.1        # Klinik doğruluk ve akıcı sentez
QA_MAX_OUTPUT_TOKENS = 3500 # Kapsamlı klinik açıklamalar ve kaynak alıntıları için tam bütçe
