"""
RAG Retrieval Değerlendiricisi.
LLM maliyeti olmadan Katmanlı Retriever (Dense + BM25 + Kota + RRF) başarımını ölçer.
Recall@K, MRR ve Eşik ROC/F1 optimizasyonu hesaplar.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from rag.eval.schema import (
    GoldenQuestion,
    RetrievalResultItem,
    RetrievedChunkInfo,
    RetrievalSummary,
    ThresholdSweepPoint,
)
from rag.retriever import Retriever, RetrievalResponse
from rag.config import MAX_DISTANCE_THRESHOLD

logger = logging.getLogger(__name__)


class RetrievalEvaluator:
    """
    Retriever başarımını altın set üzerinde ölçen modül.
    """

    def __init__(self, retriever: Retriever) -> None:
        self._retriever = retriever

    def evaluate_question(
        self,
        question: GoldenQuestion,
        top_k: int = 5,
        threshold: float = MAX_DISTANCE_THRESHOLD,
    ) -> RetrievalResultItem:
        """
        Tek bir soru için retrieval başarımını ölçer.
        """
        response: RetrievalResponse = self._retriever.retrieve(
            query=question.soru,
            top_k=top_k,
        )

        retrieved_items: List[RetrievedChunkInfo] = []
        first_expected_rank: Optional[int] = None

        for idx, hit in enumerate(response.hits, start=1):
            source_code = hit.source_code
            doc_page = hit.doc_page
            distance = hit.distance
            heading = hit.heading or ""
            text = hit.text or ""

            # Bu chunk beklenen kaynak ve sayfalardan biri mi?
            # Sayfa için +/- 1 sayfa toleransı verilir (bölüm sınırları ve başlık kaymaları için)
            is_expected = False
            for exp in question.beklenen_kaynaklar:
                if exp.source_code == source_code:
                    for p in exp.sayfalar:
                        if abs(p - doc_page) <= 1:
                            is_expected = True
                            break
                if is_expected:
                    break

            if is_expected and first_expected_rank is None:
                first_expected_rank = idx

            retrieved_items.append(
                RetrievedChunkInfo(
                    source_code=source_code,
                    doc_page=doc_page,
                    heading=heading,
                    distance=round(distance, 4),
                    text_snippet=text[:120].replace("\n", " "),
                    is_expected=is_expected,
                )
            )

        min_distance = min([h.distance for h in retrieved_items]) if retrieved_items else 2.0
        passed_threshold = response.found and (min_distance <= threshold)

        # Hit@K hesaplamaları
        hit_at_1 = any(h.is_expected for h in retrieved_items[:1])
        hit_at_3 = any(h.is_expected for h in retrieved_items[:3])
        hit_at_5 = any(h.is_expected for h in retrieved_items[:5])

        reciprocal_rank = 0.0
        if first_expected_rank is not None and first_expected_rank <= top_k:
            reciprocal_rank = 1.0 / first_expected_rank

        return RetrievalResultItem(
            question_id=question.id,
            soru=question.soru,
            tur=question.tur,
            kapsam_ici=question.kapsam_ici,
            min_distance=round(min_distance, 4),
            retrieved_hits=retrieved_items[:top_k],
            hit_at_1=hit_at_1,
            hit_at_3=hit_at_3,
            hit_at_5=hit_at_5,
            reciprocal_rank=round(reciprocal_rank, 4),
            passed_threshold=passed_threshold,
        )

    def run(
        self,
        questions: List[GoldenQuestion],
        top_k: int = 5,
        threshold: float = MAX_DISTANCE_THRESHOLD,
    ) -> Tuple[List[RetrievalResultItem], RetrievalSummary]:
        """
        Tüm altın seti değerlendirir ve özet metrikleri üretir.
        """
        results: List[RetrievalResultItem] = []
        for q in questions:
            res = self.evaluate_question(q, top_k=top_k, threshold=threshold)
            results.append(res)

        in_scope_results = [r for r in results if r.kapsam_ici]
        kapsam_ici_count = len(in_scope_results)
        kapsam_disi_count = len(results) - kapsam_ici_count

        # Sıralama Metrikleri (sadece kapsam içi sorularda anlamlı)
        if kapsam_ici_count > 0:
            recall_at_1 = sum(1 for r in in_scope_results if r.hit_at_1) / kapsam_ici_count
            recall_at_3 = sum(1 for r in in_scope_results if r.hit_at_3) / kapsam_ici_count
            recall_at_5 = sum(1 for r in in_scope_results if r.hit_at_5) / kapsam_ici_count
            mrr = sum(r.reciprocal_rank for r in in_scope_results) / kapsam_ici_count
        else:
            recall_at_1 = recall_at_3 = recall_at_5 = mrr = 0.0

        # Kaynak Bazlı Analiz (TR2025 vs EG2025)
        tr_q_count = 0
        tr_q_hit = 0
        eg_q_count = 0
        eg_q_hit = 0

        # Kategori Bazlı Recall@5
        category_counts: Dict[str, int] = defaultdict(int)
        category_hits: Dict[str, int] = defaultdict(int)

        for q, r in zip(questions, results):
            if not q.kapsam_ici:
                continue
            category_counts[q.tur] += 1
            if r.hit_at_5:
                category_hits[q.tur] += 1

            has_tr = any(exp.source_code == "TR2025" for exp in q.beklenen_kaynaklar)
            has_eg = any(exp.source_code == "EG2025" for exp in q.beklenen_kaynaklar)

            if has_tr:
                tr_q_count += 1
                if any(h.is_expected and h.source_code == "TR2025" for h in r.retrieved_hits):
                    tr_q_hit += 1

            if has_eg:
                eg_q_count += 1
                if any(h.is_expected and h.source_code == "EG2025" for h in r.retrieved_hits):
                    eg_q_hit += 1

        tr2025_recall = (tr_q_hit / tr_q_count) if tr_q_count > 0 else 0.0
        eg2025_recall = (eg_q_hit / eg_q_count) if eg_q_count > 0 else 0.0
        cross_lingual_recall = eg2025_recall  # Türkçe soru → İngilizce kılavuz getirme başarımı

        kategori_bazli_recall = {
            cat: round((category_hits[cat] / category_counts[cat]), 4)
            for cat in category_counts
        }

        # ─── Eşik Optimizasyonu (Threshold Sweep Curve) ───────────────────────
        sweep_points: List[ThresholdSweepPoint] = []
        best_threshold = threshold
        best_f1 = -1.0
        current_threshold_f1 = 0.0

        for t_int in range(20, 86, 1):  # 0.20'den 0.85'e 0.01 adımlarla
            t = t_int / 100.0
            tp = fp = tn = fn = 0

            for q, r in zip(questions, results):
                predicted_in_scope = (r.min_distance <= t)
                actual_in_scope = q.kapsam_ici

                if predicted_in_scope and actual_in_scope:
                    tp += 1
                elif predicted_in_scope and not actual_in_scope:
                    fp += 1
                elif not predicted_in_scope and not actual_in_scope:
                    tn += 1
                else:
                    fn += 1

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
            acc = (tp + tn) / len(questions) if questions else 0.0

            point = ThresholdSweepPoint(
                threshold=t,
                precision=round(prec, 4),
                recall=round(rec, 4),
                f1=round(f1, 4),
                accuracy=round(acc, 4),
                tp=tp,
                fp=fp,
                tn=tn,
                fn=fn,
            )
            sweep_points.append(point)

            if f1 > best_f1:
                best_f1 = f1
                best_threshold = t

            if abs(t - threshold) < 0.005:
                current_threshold_f1 = f1

        summary = RetrievalSummary(
            total_questions=len(questions),
            kapsam_ici_count=kapsam_ici_count,
            kapsam_disi_count=kapsam_disi_count,
            recall_at_1=round(recall_at_1, 4),
            recall_at_3=round(recall_at_3, 4),
            recall_at_5=round(recall_at_5, 4),
            mrr=round(mrr, 4),
            tr2025_recall_at_5=round(tr2025_recall, 4),
            eg2025_recall_at_5=round(eg2025_recall, 4),
            cross_lingual_recall_at_5=round(cross_lingual_recall, 4),
            kategori_bazli_recall=kategori_bazli_recall,
            current_threshold=round(threshold, 2),
            current_threshold_f1=round(current_threshold_f1, 4),
            optimal_threshold=round(best_threshold, 2),
            optimal_threshold_f1=round(best_f1, 4),
            sweep_curve=sweep_points,
        )

        return results, summary
