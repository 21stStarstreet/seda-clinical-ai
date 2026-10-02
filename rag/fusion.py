"""
Reciprocal Rank Fusion (RRF) ve Kaynak Başına Kota Motoru.
Dense (vektör) ve Lexical (BM25) sıralamalarını birleştirir,
Türkçe ve İngilizce kılavuzlar arasında adil temsil (kota) sağlar.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

RRF_K_CONSTANT = 60  # Standart RRF sabiti


def _chunk_key(doc: dict) -> str:
    """Bir chunk için benzersiz anahtar üretir (kaynak + sayfa + metin başı)."""
    text_prefix = doc.get("text", "")[:80].strip()
    return f"{doc.get('source_code', '')}:{doc.get('doc_page', 0)}:{text_prefix}"


def reciprocal_rank_fusion(
    ranked_lists: List[Tuple[List[dict], float]],  # list of (doc_list, weight)
    k: int = RRF_K_CONSTANT,
) -> List[dict]:
    """
    Standart Reciprocal Rank Fusion (RRF) formülü:
        Score(d) = Sum_i ( w_i / (k + rank_i(d)) )
    """
    scores: Dict[str, float] = {}
    doc_map: Dict[str, dict] = {}
    dense_ranks: Dict[str, int] = {}
    bm25_ranks: Dict[str, int] = {}

    for list_idx, (docs, weight) in enumerate(ranked_lists):
        is_dense = (list_idx == 0)
        for rank, doc in enumerate(docs, start=1):
            key = _chunk_key(doc)
            if key not in doc_map:
                doc_map[key] = doc.copy()

            if is_dense and key not in dense_ranks:
                dense_ranks[key] = rank
            elif not is_dense and key not in bm25_ranks:
                bm25_ranks[key] = rank

            rrf_contrib = weight / (k + rank)
            scores[key] = scores.get(key, 0.0) + rrf_contrib

    sorted_keys = sorted(scores.keys(), key=lambda k_id: scores[k_id], reverse=True)

    fused_results: List[dict] = []
    for key in sorted_keys:
        doc = doc_map[key]
        doc["rrf_score"] = round(scores[key], 5)
        doc["dense_rank"] = dense_ranks.get(key)
        doc["bm25_rank"] = bm25_ranks.get(key)
        fused_results.append(doc)

    return fused_results


def apply_source_quota_and_diversity(
    fused_docs: List[dict],
    top_k: int = 5,
    min_per_source: int = 2,
    max_per_page: int = 2,
    has_source_filter: bool = False,
) -> List[dict]:
    """
    Kaynak Başına Kota ve Sayfa Çeşitliliği Uygular:
    - has_source_filter=False ise (çapraz kılavuz sorgusu):
      TR2025'ten en az min_per_source, EG2025'ten en az min_per_source garanti edilir.
    - Aynı sayfadan en fazla max_per_page chunk alınır.
    """
    if has_source_filter or len(fused_docs) <= top_k:
        # Tek kaynak seçilmişse kota uygulamaya gerek yok
        selected = []
        page_counts: Dict[str, int] = {}
        for doc in fused_docs:
            p_key = f"{doc['source_code']}:{doc['doc_page']}"
            if page_counts.get(p_key, 0) < max_per_page:
                page_counts[p_key] = page_counts.get(p_key, 0) + 1
                selected.append(doc)
            if len(selected) >= top_k:
                break
        return selected

    # Kaynakları ayır
    tr_docs = [d for d in fused_docs if d.get("source_code") == "TR2025"]
    eg_docs = [d for d in fused_docs if d.get("source_code") == "EG2025"]

    selected_keys = set()
    final_selection: List[dict] = []
    page_counts: Dict[str, int] = {}

    def try_add(doc: dict) -> bool:
        key = _chunk_key(doc)
        if key in selected_keys:
            return False
        p_key = f"{doc['source_code']}:{doc['doc_page']}"
        if page_counts.get(p_key, 0) >= max_per_page:
            return False
        page_counts[p_key] = page_counts.get(p_key, 0) + 1
        selected_keys.add(key)
        final_selection.append(doc)
        return True

    # 1. Faz: Her kaynaktan en az min_per_source kota sağla
    tr_added = 0
    for doc in tr_docs:
        if tr_added >= min_per_source:
            break
        if try_add(doc):
            tr_added += 1

    eg_added = 0
    for doc in eg_docs:
        if eg_added >= min_per_source:
            break
        if try_add(doc):
            eg_added += 1

    # 2. Faz: Kalan boşlukları genel RRF skoruna göre en iyi olanlarla doldur
    for doc in fused_docs:
        if len(final_selection) >= top_k:
            break
        try_add(doc)

    # Nihai listeyi RRF skoruna göre yeniden sırala
    final_selection.sort(key=lambda d: d.get("rrf_score", 0.0), reverse=True)
    return final_selection[:top_k]
