"""
RAG Sistematik Değerlendirme Koşucusu (Runner & CLI).
Tek komutla çalışır, sonuçları terminalde Rich ile gösterir ve tarihli rapor kaydeder.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from rag.eval.schema import (
    GoldenQuestion,
    EvalReport,
    RetrievalSummary,
    GenerationSummary,
)
from rag.eval.retrieval_evaluator import RetrievalEvaluator
from rag.eval.generation_evaluator import GenerationEvaluator
from rag.embedder import Embedder
from rag.store import VectorStore
from rag.retriever import Retriever
from rag.qa_engine import QAEngine
from rag.config import MAX_DISTANCE_THRESHOLD, EMBEDDING_MODEL, QA_MODEL

console = Console()


def load_golden_set(filepath: str) -> List[GoldenQuestion]:
    """Altın soru setini JSON dosyasından yükler."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Altın set bulunamadı: {filepath}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [GoldenQuestion.model_validate(item) for item in data]


def save_reports(report: EvalReport, output_dir: str) -> Tuple[Path, Path]:
    """Değerlendirme sonucunu hem Markdown hem JSON olarak kaydeder."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = out_path / f"rag_eval_{timestamp}.json"
    md_file = out_path / f"rag_eval_{timestamp}.md"

    # 1. JSON
    with open(json_file, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))

    # 2. Markdown Raporu
    ret = report.retrieval
    md_content = f"""# SEDA RAG Sistematik Değerlendirme Raporu

- **Tarih:** {report.timestamp}
- **Altın Set:** `{report.golden_set_path}` (mtime: `{report.golden_set_mtime}`)
- **Embedding Modeli:** `{report.embedding_model}`
- **QA Modeli:** `{report.model_version}`
- **Toplam Test Sorusu:** {ret.total_questions} ({ret.kapsam_ici_count} kapsam içi, {ret.kapsam_disi_count} kapsam dışı)

---

## 1. Retrieval (Getirme) Metrikleri

| Metrik | Değer | Hedef Standart | Durum |
|---|---|---|---|
| **Recall@1** | %{ret.recall_at_1 * 100:.1f} | ≥ %70.0 | {'✅' if ret.recall_at_1 >= 0.70 else '⚠️'} |
| **Recall@3** | %{ret.recall_at_3 * 100:.1f} | ≥ %85.0 | {'✅' if ret.recall_at_3 >= 0.85 else '⚠️'} |
| **Recall@5** | %{ret.recall_at_5 * 100:.1f} | ≥ %90.0 | {'✅' if ret.recall_at_5 >= 0.90 else '⚠️'} |
| **MRR (Mean Reciprocal Rank)** | {ret.mrr:.3f} | ≥ 0.750 | {'✅' if ret.mrr >= 0.75 else '⚠️'} |
| **TR2025 Recall@5** | %{ret.tr2025_recall_at_5 * 100:.1f} | ≥ %90.0 | {'✅' if ret.tr2025_recall_at_5 >= 0.90 else '⚠️'} |
| **EG2025 (Cross-Lingual) Recall@5** | %{ret.cross_lingual_recall_at_5 * 100:.1f} | ≥ %80.0 | {'✅' if ret.cross_lingual_recall_at_5 >= 0.80 else '⚠️'} |

### Kategori Bazlı Başarım (Recall@5)
"""
    for cat, score in ret.kategori_bazli_recall.items():
        md_content += f"- **{cat}:** %{score * 100:.1f}\n"

    md_content += f"""
---

## 2. Eşik (Distance Threshold) Analizi

- **Mevcut Eşik:** `{ret.current_threshold}` (F1: `{ret.current_threshold_f1:.3f}`)
- **Matematiksel Optimal Eşik:** `{ret.optimal_threshold}` (F1: `{ret.optimal_threshold_f1:.3f}`)

> **Değerlendirme:** Mevcut eşik ({ret.current_threshold}), F1 eğrisinin optimal noktasına ({ret.optimal_threshold}) {'oldukça yakındır.' if abs(ret.current_threshold - ret.optimal_threshold) <= 0.04 else 'göre yeniden kalibre edilebilir.'}

"""

    if report.generation:
        gen = report.generation
        md_content += f"""---

## 3. Generation (Üretim & Güvenilirlik) Metrikleri

| Metrik | Değer | Hedef Standart | Durum |
|---|---|---|---|
| **Doğru Çekimserlik (Proper Refusal)** | %{gen.proper_refusal_rate * 100:.1f} | %100.0 | {'✅' if gen.proper_refusal_rate >= 0.95 else '⚠️'} |
"""
        if gen.yanlis_oncul_stats:
            yo = gen.yanlis_oncul_stats
            pct = (yo.get("basarili", 0) / yo["toplam"] * 100) if yo.get("toplam") else 100.0
            md_content += f"| └─ **Yanlış Öncül Yönetimi** | %{pct:.1f} ({yo.get('basarili', 0)}/{yo.get('toplam', 0)}) | Çürüttü: {yo.get('curuttu', 0)}, Reddetti: {yo.get('reddetti', 0)}, Hata: {yo.get('hata', 0)} | {'✅' if pct >= 80 else '⚠️'} |\n"

        md_content += f"""| **Atıf Doğruluğu (Citation Precision)** | %{gen.mean_citation_precision * 100:.1f} | ≥ %95.0 | {'✅' if gen.mean_citation_precision >= 0.95 else '⚠️'} |
| **Alıntı Sadakati (Quote Veracity)** | %{gen.mean_quote_veracity * 100:.1f} | ≥ %90.0 | {'✅' if gen.mean_quote_veracity >= 0.90 else '⚠️'} |
| **Kilit Nokta Kapsaması (Coverage)** | %{gen.mean_keypoint_coverage * 100:.1f} | ≥ %85.0 | {'✅' if gen.mean_keypoint_coverage >= 0.85 else '⚠️'} |
| **Sayısal Doğruluk (Doz & Eşik)** | %{gen.mean_numerical_accuracy * 100:.1f} | ≥ %95.0 | {'✅' if gen.mean_numerical_accuracy >= 0.95 else '⚠️'} |
| **Ortalama Yanıt Süresi** | {gen.avg_latency_ms:.0f} ms | ≤ 2500 ms | {'✅' if gen.avg_latency_ms <= 2500 else '⏱'} |
"""
        if gen.fallback_count > 0:
            fb_pct = (gen.fallback_count / gen.total_evaluated) * 100
            md_content += f"""
### ⚠️ Fallback / Timeout Soruları ({gen.fallback_count} soru, %{fb_pct:.1f} — Metriklerden Hariç Tutuldu)

| Soru ID | Soru | Neden |
|---|---|---|
"""
            for fq in gen.fallback_questions:
                md_content += f"| `{fq.get('id', '')}` | {fq.get('soru', '')} | {fq.get('neden', '')} |\n"


    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    return md_file, json_file


def run_evaluation(
    golden_set_path: str = "rag/eval/golden_set.json",
    top_k: int = 5,
    threshold: float = MAX_DISTANCE_THRESHOLD,
    full: bool = False,
    category_filter: Optional[str] = None,
    output_dir: str = "reports/rag_eval",
) -> EvalReport:
    """Değerlendirmeyi baştan sona icra eder."""

    console.print(Panel.fit(
        "[bold cyan]🩺 SEDA CDSS — RAG Sistematik Değerlendirme Motoru[/bold cyan]\n"
        "[dim]Klinik Kılavuz Retrieval ve Generation Başarım Denetimi[/dim]",
        border_style="cyan"
    ))

    # 1. Altın Seti Yükle
    p = Path(golden_set_path)
    if p.exists():
        golden_set_mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    else:
        golden_set_mtime = "Bilinmiyor"

    questions = load_golden_set(golden_set_path)
    if category_filter:
        questions = [q for q in questions if q.tur == category_filter]
        console.print(f"[yellow]Filtre uygulandı: Sadece '{category_filter}' kategorisinden {len(questions)} soru.[/yellow]")

    console.print(f"📥 Altın Set Yüklendi: [bold green]{len(questions)}[/bold green] soru — \\[{golden_set_path} | mtime: {golden_set_mtime}\\]")

    # 2. Servisleri Başlat
    embedder = Embedder()
    store = VectorStore()
    retriever = Retriever(embedder, store)
    retrieval_eval = RetrievalEvaluator(retriever)

    # 3. Retrieval Değerlendirmesi
    console.print("\n[bold]1. Retrieval Değerlendirmesi Başlatılıyor (ChromaDB Vector Search)...[/bold]")
    ret_items, ret_summary = retrieval_eval.run(questions, top_k=top_k, threshold=threshold)

    # Tablo 1: Retrieval Özet
    t1 = Table(title="📊 Retrieval Metrikleri", header_style="bold magenta")
    t1.add_column("Metrik", style="cyan")
    t1.add_column("Sonuç", justify="right")
    t1.add_column("Hedef", justify="right")
    t1.add_column("Durum", justify="center")

    t1.add_row("Recall@1", f"%{ret_summary.recall_at_1 * 100:.1f}", "≥ %70", "✅" if ret_summary.recall_at_1 >= 0.70 else "⚠️")
    t1.add_row("Recall@3", f"%{ret_summary.recall_at_3 * 100:.1f}", "≥ %85", "✅" if ret_summary.recall_at_3 >= 0.85 else "⚠️")
    t1.add_row("Recall@5", f"%{ret_summary.recall_at_5 * 100:.1f}", "≥ %90", "✅" if ret_summary.recall_at_5 >= 0.90 else "⚠️")
    t1.add_row("MRR (Mean Reciprocal Rank)", f"{ret_summary.mrr:.3f}", "≥ 0.75", "✅" if ret_summary.mrr >= 0.75 else "⚠️")
    t1.add_row("TR2025 Recall@5", f"%{ret_summary.tr2025_recall_at_5 * 100:.1f}", "≥ %90", "✅" if ret_summary.tr2025_recall_at_5 >= 0.90 else "⚠️")
    t1.add_row("EG2025 (Cross-Lingual) Recall@5", f"%{ret_summary.cross_lingual_recall_at_5 * 100:.1f}", "≥ %80", "✅" if ret_summary.cross_lingual_recall_at_5 >= 0.80 else "⚠️")
    console.print(t1)

    # Tablo 2: Kategori Bazlı Recall
    t2 = Table(title="🏷️ Kategori Bazlı Recall@5", header_style="bold blue")
    t2.add_column("Kategori", style="yellow")
    t2.add_column("Recall@5", justify="right")
    for cat, score in ret_summary.kategori_bazli_recall.items():
        t2.add_row(cat, f"%{score * 100:.1f}")
    console.print(t2)

    # Tablo 3: Eşik Optimizasyonu
    t3 = Table(title="🎯 Mesafe Eşiği (Threshold) Analizi", header_style="bold green")
    t3.add_column("Metrik", style="white")
    t3.add_column("Değer", justify="right")
    t3.add_row("Mevcut Eşik", f"{ret_summary.current_threshold:.2f}")
    t3.add_row("Mevcut Eşik F1 Skoru", f"{ret_summary.current_threshold_f1:.3f}")
    t3.add_row("Matematiksel Optimal Eşik", f"[bold green]{ret_summary.optimal_threshold:.2f}[/bold green]")
    t3.add_row("Optimal Eşik F1 Skoru", f"[bold green]{ret_summary.optimal_threshold_f1:.3f}[/bold green]")
    console.print(t3)

    gen_summary: Optional[GenerationSummary] = None
    gen_items = []

    # 4. Generation Değerlendirmesi (Opsiyonel / --full)
    if full:
        console.print("\n[bold]2. Generation Değerlendirmesi Başlatılıyor (Gemini QA Engine)...[/bold]")
        qa_engine = QAEngine()
        gen_eval = GenerationEvaluator(qa_engine, retriever)
        gen_items, gen_summary = gen_eval.run(questions)

        t4 = Table(title="🧠 Generation & Güvenilirlik Metrikleri", header_style="bold red")
        t4.add_column("Metrik", style="cyan")
        t4.add_column("Sonuç", justify="right")
        t4.add_column("Hedef", justify="right")
        t4.add_column("Durum", justify="center")

        t4.add_row("Doğru Çekimserlik (Proper Refusal)", f"%{gen_summary.proper_refusal_rate * 100:.1f}", "%100", "✅" if gen_summary.proper_refusal_rate >= 0.95 else "⚠️")
        if gen_summary.yanlis_oncul_stats:
            yo = gen_summary.yanlis_oncul_stats
            pct = (yo.get("basarili", 0) / yo["toplam"] * 100) if yo.get("toplam") else 100.0
            yo_detail = f"Çürüttü: {yo.get('curuttu', 0)}, Reddetti: {yo.get('reddetti', 0)}, Hata: {yo.get('hata', 0)}"
            t4.add_row("  └─ Yanlış Öncül Yönetimi", f"%{pct:.1f} ({yo.get('basarili', 0)}/{yo.get('toplam', 0)})", yo_detail, "✅" if pct >= 80 else "⚠️")

        t4.add_row("Atıf Doğruluğu (Citation Precision)", f"%{gen_summary.mean_citation_precision * 100:.1f}", "≥ %95", "✅" if gen_summary.mean_citation_precision >= 0.95 else "⚠️")
        t4.add_row("Alıntı Sadakati (Quote Veracity)", f"%{gen_summary.mean_quote_veracity * 100:.1f}", "≥ %90", "✅" if gen_summary.mean_quote_veracity >= 0.90 else "⚠️")
        t4.add_row("Kilit Nokta Kapsaması", f"%{gen_summary.mean_keypoint_coverage * 100:.1f}", "≥ %85", "✅" if gen_summary.mean_keypoint_coverage >= 0.85 else "⚠️")
        t4.add_row("Sayısal Değer Doğruluğu", f"%{gen_summary.mean_numerical_accuracy * 100:.1f}", "≥ %95", "✅" if gen_summary.mean_numerical_accuracy >= 0.95 else "⚠️")
        t4.add_row("Ortalama Yanıt Süresi", f"{gen_summary.avg_latency_ms:.0f} ms", "≤ 2500 ms", "✅" if gen_summary.avg_latency_ms <= 2500 else "⏱")
        console.print(t4)

        if gen_summary.fallback_count > 0:
            fb_pct = (gen_summary.fallback_count / gen_summary.total_evaluated) * 100
            fb_table = Table(
                title=f"⚠️ Fallback/Timeout Soruları: {gen_summary.fallback_count} soru (%{fb_pct:.1f}) — metriklerden hariç tutuldu",
                header_style="bold yellow"
            )
            fb_table.add_column("Soru ID", style="cyan", width=8)
            fb_table.add_column("Soru", style="white")
            fb_table.add_column("Neden", style="red")
            for fq in gen_summary.fallback_questions:
                fb_table.add_row(fq.get("id", ""), fq.get("soru", ""), fq.get("neden", ""))
            console.print(fb_table)
    else:
        console.print("\n[dim]ℹ️ Generation testi atlandı. LLM yanıt doğrulaması için '--full' bayrağını kullanın.[/dim]")

    # 5. Raporu Kaydet
    report = EvalReport(
        golden_set_path=golden_set_path,
        golden_set_mtime=golden_set_mtime,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        model_version=QA_MODEL,
        embedding_model=EMBEDDING_MODEL,
        retrieval=ret_summary,
        generation=gen_summary,
        itemized_retrieval=ret_items,
        itemized_generation=gen_items,
    )

    md_file, json_file = save_reports(report, output_dir)
    console.print(f"\n[bold green]✅ Değerlendirme Tamamlandı![/bold green]")
    console.print(f"📄 Markdown Raporu: [underline]{md_file}[/underline]")
    console.print(f"📦 JSON Verisi:     [underline]{json_file}[/underline]\n")

    return report


def main():
    parser = argparse.ArgumentParser(description="SEDA RAG Sistematik Değerlendirme")
    parser.add_argument("--golden-set", default="rag/eval/golden_set.json", help="Altın set JSON dosyası yolu")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K retrieval sayısı")
    parser.add_argument("--threshold", type=float, default=MAX_DISTANCE_THRESHOLD, help="Test edilecek mesafe eşiği")
    parser.add_argument("--full", action="store_true", help="Gemini QA Engine ile tam üretim testini de çalıştırır")
    parser.add_argument("--category", default=None, help="Sadece belirli bir soru türünü filtrele")
    parser.add_argument("--output-dir", default="reports/rag_eval", help="Raporların kaydedileceği dizin")

    args = parser.parse_args()

    run_evaluation(
        golden_set_path=args.golden_set,
        top_k=args.top_k,
        threshold=args.threshold,
        full=args.full,
        category_filter=args.category,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
