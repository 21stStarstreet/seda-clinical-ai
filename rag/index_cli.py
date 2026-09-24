"""
Tek Seferlik Indexleme Scripti.
PDF'leri parse eder, chunk'lar, embed eder ve ChromaDB'ye kaydeder.

Kullanım:
    python -m rag.index_cli            # Eksik kaynakları artımlı indexle
    python -m rag.index_cli --force    # Tüm DB'yi silerek yeniden indexle
    python -m rag.index_cli --check    # Mevcut durumu raporla
    python -m rag.index_cli --source EG2025           # Sadece EG2025'i ekle (TR2025'e dokunma)
    python -m rag.index_cli --source EG2025 --force   # EG2025'i silip yeniden indexle

Artımlı Mantık (--force olmadan):
    Her kaynak bağımsız değerlendirilir. Zaten indekslenmiş kaynaklar
    atlanır, eksik olanlar eklenir. Mevcut chunk'lar korunur (upsert).

    Örnek: TR2025 indeksli, EG2025 eksik:
        python -m rag.index_cli          → Sadece EG2025'i indexler
        python -m rag.index_cli --force  → Her ikisini de sıfırdan indexler

Chunk ID Formatı: '{source_code}_p{doc_page}_c{chunk_index}'
    → Deterministik. Aynı kaynak iki kez indexlenirse upsert
      ile tekrar yazılır, duplicate oluşmaz.
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
        description="SEDA RAG — Klinik Kılavuz İndexleme Aracı",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "--source belirtilmişse: o kaynağı sil ve yeniden indexle. "
            "--source belirtilmemişse: TÜM DB'yi sil ve yeniden indexle."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Mevcut indexleme durumunu raporla, işlem yapma.",
    )
    parser.add_argument(
        "--source",
        choices=["TR2025", "EG2025"],
        default=None,
        help=(
            "Sadece belirtilen kaynağı işle. "
            "Belirtilmezse eksik tüm kaynaklar işlenir."
        ),
    )
    return parser.parse_args()


def _print_banner() -> None:
    print()
    print("━" * 58)
    print("  SEDA RAG — Klinik Kılavuz İndexleyici")
    print("━" * 58)


def _index_single_source(
    source_code: str,
    store,
    force_this_source: bool,
) -> bool:
    """
    Tek bir kaynağı indexle.

    Args:
        source_code:        'TR2025' veya 'EG2025'
        store:              VectorStore örneği
        force_this_source:  True → mevcut chunk'ları sil, yeniden indexle

    Returns:
        True: indeksleme başarılı | False: atlandı veya hata
    """
    from rag.extractor import PDFExtractor
    from rag.chunker import Chunker
    from rag.embedder import Embedder

    existing_count = store.chunk_count_by_source(source_code)

    # ── Force silme kontrolü ──────────────────────────────────────
    if existing_count > 0 and force_this_source:
        print(f"\n  [{source_code}] 🗑  Mevcut {existing_count} chunk siliniyor...")
        store.delete_by_source(source_code)
        print(f"  [{source_code}] ✓  Silindi.")

    # ── PDF'den metin çıkar ───────────────────────────────────────
    print(f"\n  [{source_code}] 📄 PDF metin çıkarılıyor...")
    t0 = time.time()
    extractor = PDFExtractor()
    try:
        pages = list(extractor.extract_source(source_code))
    except FileNotFoundError as exc:
        print(f"\n  [{source_code}] ❌ PDF bulunamadı: {exc}")
        print(f"  [{source_code}]    docs/guidelines/ klasörüne kopyalayın ve tekrar deneyin.")
        return False
    except Exception as exc:
        print(f"\n  [{source_code}] ❌ PDF çıkarma hatası: {exc}")
        return False

    if not pages:
        print(f"\n  [{source_code}] ⚠️  Geçerli sayfa bulunamadı — PDF boş veya okunamıyor.")
        return False

    # ── Chunk'la ──────────────────────────────────────────────────
    print(f"  [{source_code}] ✂️  Chunk'lanıyor ({len(pages)} sayfa)...")
    chunker = Chunker()
    chunks = chunker.chunk_pages(pages)
    t1 = time.time()
    print(f"  [{source_code}] ✓  {len(chunks)} chunk üretildi ({t1 - t0:.1f}s)")

    if not chunks:
        print(f"\n  [{source_code}] ⚠️  Hiç chunk üretilmedi.")
        return False

    # ── Checkpointing / Resume Kontrolü ───────────────────────────
    from rag.config import EMBEDDING_BATCH_SIZE, EMBEDDING_DELAY_SEC
    existing_ids = store.get_existing_chunk_ids(source_code)
    pending_chunks = [c for c in chunks if c.chunk_id not in existing_ids]

    if not pending_chunks:
        print(f"\n  [{source_code}] ✅ Tüm {len(chunks)} chunk zaten ChromaDB'de mevcut.")
        return True

    already_done = len(chunks) - len(pending_chunks)
    if already_done > 0:
        print(f"  [{source_code}] ℹ️  Checkpoint bulundu: {already_done} chunk zaten kayıtlı.")
        print(f"  [{source_code}]    Kalan {len(pending_chunks)} chunk işleniyor (Resume modu)...")

    # ── Tahmini süre bilgisi ──────────────────────────────────────
    batch_count = (len(pending_chunks) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
    estimated_sec = batch_count * EMBEDDING_DELAY_SEC
    print(f"\n  [{source_code}] 🔢 Embedding & Kayıt başlatılıyor...")
    print(f"  [{source_code}]    Kalan: {len(pending_chunks)} chunk — {batch_count} batch (Batch boyutu: {EMBEDDING_BATCH_SIZE})")
    print(f"  [{source_code}]    Tahmini süre: ~{int(estimated_sec) // 60}dk {int(estimated_sec) % 60}s (Free Tier rate limit koruması)")

    # ── Batch bazında Embed et ve ANINDA ChromaDB'ye Kaydet ───────
    embedder = Embedder()
    t_start_batches = time.time()

    for b_idx in range(0, len(pending_chunks), EMBEDDING_BATCH_SIZE):
        batch = pending_chunks[b_idx: b_idx + EMBEDDING_BATCH_SIZE]
        batch_texts = [c.text for c in batch]

        try:
            batch_embeddings = embedder.embed_documents(batch_texts)
            store.add_chunks(batch, batch_embeddings)  # Anında diske yaz
        except Exception as exc:
            saved_so_far = store.chunk_count_by_source(source_code)
            print(f"\n  [{source_code}] ❌ Embedding hatası: {exc}")
            print(f"  [{source_code}] 💾 Şu ana kadar {saved_so_far}/{len(chunks)} chunk güvenle ChromaDB'ye kaydedildi.")
            print(f"  [{source_code}]    Tekrar çalıştırıldığında kaldığı yerden devam edecektir.")
            return False

        current_total = already_done + min(b_idx + EMBEDDING_BATCH_SIZE, len(pending_chunks))
        pct = current_total * 100 // len(chunks)
        print(f"  [{source_code}]    ✓ Kaydedildi: {current_total}/{len(chunks)} (%{pct})", flush=True)

        # Son batch değilse rate limit için bekle
        if b_idx + EMBEDDING_BATCH_SIZE < len(pending_chunks):
            time.sleep(EMBEDDING_DELAY_SEC)

    t_end = time.time()
    final_count = store.chunk_count_by_source(source_code)
    total_elapsed = t_end - t0
    print(f"\n  [{source_code}] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  [{source_code}] ✅ İNDEXLEME TAMAMLANDI: {final_count} chunk ({total_elapsed:.1f}s)")
    print(f"  [{source_code}] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return True


def run_indexing(force: bool = False, source_filter: str | None = None) -> None:
    """
    Ana indexleme koordinatörü.

    Artımlı mantık:
        - source_filter belirtilmişse: sadece o kaynak işlenir
        - source_filter None ise: eksik tüm kaynaklar sırayla işlenir
        - force=True + source_filter=None: TÜM koleksiyon sıfırlanır
        - force=True + source_filter='X': sadece X silinip yeniden indexlenir
    """
    from rag.store import VectorStore
    from rag.config import SOURCES

    store = VectorStore()

    # ── TÜM koleksiyonu sıfırla (force, kaynak filtresi YOK) ──────
    if force and source_filter is None:
        total_before = store.chunk_count
        if total_before > 0:
            print(f"\n🗑  TÜM koleksiyon sıfırlanıyor ({total_before} chunk)...")
            store.reset()
            print("✓  Koleksiyon sıfırlandı.")

    # ── İşlenecek kaynakları belirle ──────────────────────────────
    sources_to_process = (
        [source_filter]
        if source_filter
        else list(SOURCES.keys())
    )

    print()
    print("━" * 58)
    print(f"  İşlenecek kaynak(lar): {', '.join(sources_to_process)}")
    print("━" * 58)

    # ── Her kaynağı sırayla işle ──────────────────────────────────
    t_total_start = time.time()
    indexed_any = False

    for src in sources_to_process:
        # force mantığı: force + belirli kaynak = sadece o kaynak için force
        # force + tüm kaynaklar = koleksiyon zaten sıfırlandı, force=False gibi davran
        force_this = force and (source_filter is not None)

        success = _index_single_source(
            source_code=src,
            store=store,
            force_this_source=force_this,
        )
        if success:
            indexed_any = True

    # ── Final rapor ───────────────────────────────────────────────
    print()
    print("━" * 58)
    print("  FINAL DURUM")
    print("━" * 58)
    final_status = store.indexed_sources()
    total_chunks = sum(final_status.values())
    for src, count in final_status.items():
        status_icon = "✅" if count > 0 else "❌ EKSİK"
        print(f"  {status_icon:3} {src}: {count} chunk")
    print(f"\n  📦 TOPLAM: {total_chunks} chunk")
    print(f"  ⏱  Toplam süre: {time.time() - t_total_start:.1f}s")
    print("━" * 58)
    print()

    if not indexed_any:
        print("  ℹ️  Tüm kaynaklar zaten indekslenmiş, yeni işlem yapılmadı.")
        print("  💡 Zorla yeniden indexlemek için --force kullanın.")


def check_status() -> None:
    """Kaynak bazlı ChromaDB durumunu raporla."""
    from rag.store import VectorStore
    from rag.config import CHROMA_DB_PATH

    print(f"\n📂 ChromaDB Yolu: {CHROMA_DB_PATH}")
    store = VectorStore()

    print()
    print("━" * 58)
    print("  INDEXLEME DURUMU")
    print("━" * 58)

    status = store.indexed_sources()
    total = sum(status.values())
    expected = {"TR2025": 265, "EG2025": 265}

    for src, count in status.items():
        if count == 0:
            print(f"  ❌ {src}: İNDEKSLENMEMİŞ")
            print(f"       → Eklemek için: python -m rag.index_cli --source {src}")
        else:
            exp = expected.get(src, "?")
            print(f"  ✅ {src}: {count} chunk (beklenen: ~{exp})")

    print(f"\n  📦 Toplam: {total} chunk")
    if total == 0:
        print("  ⚠️  Koleksiyon boş — indexleme gerekiyor.")
        print("     Çalıştırın: python -m rag.index_cli")
    elif any(v == 0 for v in status.values()):
        print("  ⚠️  Eksik kaynaklar var — yukarıdaki komutları çalıştırın.")
    else:
        print("  ✅ Tüm kaynaklar indekslenmiş — RAG hazır.")
    print("━" * 58)
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


