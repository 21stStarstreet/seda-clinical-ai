"""
Tek Seferlik Indexleme Scripti.
PDF'leri parse eder, chunk'lar, embed eder ve ChromaDB'ye kaydeder.

Kullanım:
    python -m rag.index_cli            # normal indexleme
    python -m rag.index_cli --force    # mevcut DB'yi silerek yeniden indexle
    python -m rag.index_cli --check    # sadece mevcut durumu kontrol et
"""

from __future__ import annotations

import sys
import time
import argparse
import logging

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SEDA RAG — Kılavuz İndexleme Aracı",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Mevcut ChromaDB'yi silerek baştan indexle.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Mevcut indexleme durumunu kontrol et, işlem yapma.",
    )
    parser.add_argument(
        "--source",
        choices=["TR2025", "EG2025"],
        default=None,
        help="Sadece belirtilen kaynağı indexle.",
    )
    return parser.parse_args()


def _print_banner() -> None:
    print()
    print("━" * 55)
    print("  SEDA RAG — Klinik Kılavuz İndexleyici")
    print("━" * 55)


def run_indexing(force: bool = False, source_filter: str | None = None) -> None:
    """Ana indexleme pipeline'ı."""
    from rag.extractor import PDFExtractor
    from rag.chunker import Chunker
    from rag.embedder import Embedder
    from rag.store import VectorStore
    from rag.config import SOURCES

    store = VectorStore()

    if not force and not store.is_empty:
        print(f"\n✅ ChromaDB zaten dolu: {store.chunk_count} chunk mevcut.")
        print("   Yeniden indexlemek için --force kullanın.")
        return

    if force and not store.is_empty:
        print(f"\n🗑  Mevcut {store.chunk_count} chunk siliniyor...")
        store.reset()

    print("\n📄 1/4 PDF Metin Çıkarma...")
    t0 = time.time()

    extractor = PDFExtractor()
    chunker = Chunker()

    sources_to_index = (
        [source_filter] if source_filter else list(SOURCES.keys())
    )

    all_pages = []
    for src in sources_to_index:
        pages = list(extractor.extract_source(src))
        print(f"  [{src}] {len(pages)} sayfa çıkarıldı")
        all_pages.extend(pages)

    t1 = time.time()
    print(f"  ⏱  {t1 - t0:.1f}s")

    print("\n✂️  2/4 Metni Chunk'lara Bölme...")
    chunks = chunker.chunk_pages(all_pages)
    print(f"  Toplam chunk: {len(chunks)}")
    t2 = time.time()
    print(f"  ⏱  {t2 - t1:.1f}s")

    print("\n🔢 3/4 Embedding (Gemini text-embedding-004)...")
    print(f"  {len(chunks)} chunk × ~280 kelime ≈ API çağrısı yapılıyor...")
    embedder = Embedder()
    texts = [c.text for c in chunks]
    embeddings = embedder.embed_documents(texts)
    t3 = time.time()
    print(f"  ⏱  {t3 - t2:.1f}s")

    print("\n💾 4/4 ChromaDB'ye Kaydediliyor...")
    # Batch'ler halinde ekle (büyük koleksiyonlar için)
    BATCH = 200
    for i in range(0, len(chunks), BATCH):
        batch_chunks = chunks[i: i + BATCH]
        batch_embeddings = embeddings[i: i + BATCH]
        store.add_chunks(batch_chunks, batch_embeddings)
        print(f"  Kaydedildi: {min(i + BATCH, len(chunks))}/{len(chunks)}", end="\r")

    print()
    t4 = time.time()
    print(f"  ⏱  {t4 - t3:.1f}s")

    total = t4 - t0
    print()
    print("━" * 55)
    print(f"  ✅ İNDEXLEME TAMAMLANDI")
    print(f"  📦 Toplam chunk: {store.chunk_count}")
    print(f"  ⏱  Toplam süre: {total:.1f}s")
    print("━" * 55)
    print()


def check_status() -> None:
    """ChromaDB durumunu raporla."""
    from rag.store import VectorStore
    from rag.config import CHROMA_DB_PATH

    print(f"\n📂 ChromaDB Yolu: {CHROMA_DB_PATH}")
    store = VectorStore()
    count = store.chunk_count
    if count == 0:
        print("⚠️  Koleksiyon boş — indexleme gerekiyor.")
        print("   Çalıştırın: python -m rag.index_cli")
    else:
        print(f"✅ {count} chunk mevcut — RAG hazır.")
    print()


def main() -> None:
    _print_banner()
    args = _parse_args()

    if args.check:
        check_status()
        return

    run_indexing(force=args.force, source_filter=args.source)


if __name__ == "__main__":
    main()
