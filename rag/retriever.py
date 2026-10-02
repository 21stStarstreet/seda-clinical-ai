"""
Kılavuz Retriever — Katmanlı Hibrit Arama ve Kaynak Kotası Mimarisi.
Dense Vektör Arama + Okapi BM25 + Çift Dilli Genişletme + RRF Füzyonu.

Kalite Mekanizmaları:
    1. Hibrit Arama (Hybrid Dense + Lexical BM25):
       - İlaç isimleri, dozlar ve skorları BM25 harfi harfine yakalar.
       - Anlamsal klinik bağlamı Gemini Vektör modeli yakalar.
    2. Kaynak Başına Kota (Per-Source Quota):
       - Türkçe kılavuzun İngilizce kılavuzu kotadan elemesini önler (en az 2 TR, en az 2 EG).
    3. Çift Dilli Genişletme:
       - Tıbbi terimlerin İngilizce eşdeğerleri (gebelik → pregnancy vb.) sorguya eklenir.
    4. Distance & RRF Threshold:
       - İlgisiz sorular elenir (hallüsinasyon önleme).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, List

from rag.config import TOP_K, MAX_DISTANCE_THRESHOLD
from rag.embedder import Embedder
from rag.store import VectorStore
from rag.bm25 import BM25SearchEngine
from rag.fusion import reciprocal_rank_fusion, apply_source_quota_and_diversity
from rag.bilingual_dictionary import expand_query_bilingual

logger = logging.getLogger(__name__)


# ─── Sonuç Veri Yapısı ────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    """Tek bir ilgili chunk'ı ve meta verilerini taşır."""

    source_code: str
    display_source: str
    doc_page: int
    heading: str
    text: str
    distance: float
    rrf_score: Optional[float] = None

    @property
    def similarity_pct(self) -> int:
        """Cosine distance'ı anlaşılır benzerlik yüzdesine çevir."""
        return max(0, int((2.0 - self.distance) / 2.0 * 100))


@dataclass
class RetrievalResponse:
    """Retrieval'ın tam yanıtı."""

    query: str
    hits: list[RetrievalResult] = field(default_factory=list)
    found: bool = True

    @property
    def context_text(self) -> str:
        """LLM'e gönderilecek bağlam bloğunu üretir."""
        if not self.hits:
            return ""
        parts = []
        for i, hit in enumerate(self.hits, 1):
            parts.append(
                f"[BAĞLAM {i} — {hit.display_source}, Sayfa {hit.doc_page}"
                + (f", Bölüm: {hit.heading}" if hit.heading else "")
                + "]\n"
                + hit.text
            )
        return "\n\n".join(parts)


# ─── Katmanlı Retriever ───────────────────────────────────────────────────────

class Retriever:
    """
    Serbest metin sorusu → İki Dilli Hibrit Arama → RRF + Kaynak Kotası → Top-K.
    """

    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self._embedder = embedder
        self._store = store
        self._bm25_engine = BM25SearchEngine.get_instance(store)

    def retrieve(
        self,
        query: str,
        top_k: int = TOP_K,
        source_filter: Optional[list[str]] = None,
        use_hybrid: bool = True,
        use_source_quota: bool = True,
    ) -> RetrievalResponse:
        """
        Sorguyu embed et, Dense + BM25 ile ara, RRF ve kota ile birleştir.
        """
        if self._store.is_empty:
            return RetrievalResponse(query=query, hits=[], found=False)

        # 1. Çift Dilli Zenginleştirilmiş Vektör Sorgusu
        expanded_query = expand_query_bilingual(query)
        query_vec = self._embedder.embed_query(expanded_query)

        # 2. Dense (Vektör) Arama — Genişletilmiş aday havuzu (top_k * 3)
        candidate_count = max(top_k * 3, 15)
        dense_hits = self._store.query(
            query_embedding=query_vec,
            top_k=candidate_count,
            source_filter=source_filter,
        )

        if not dense_hits:
            return RetrievalResponse(query=query, hits=[], found=False)

        # Minimum distance kontrolü (tüm adaylar eşiğin çok üzerindeyse ilgisiz soru)
        min_dist = min([h["distance"] for h in dense_hits]) if dense_hits else 2.0
        if min_dist > MAX_DISTANCE_THRESHOLD:
            # Hibrit arama aktifse BM25 leksikal kontrolü yap (klinik anahtar kelime var mı?)
            bm25_matches = (
                self._bm25_engine.search(
                    query=query,
                    top_k=3,
                    source_filter=source_filter,
                )
                if use_hybrid
                else []
            )
            # Eğer BM25 de hiçbir şey bulamadıysa veya dense mesafe aşırı uzaksa (> 0.45) ilgisiz kabul et
            if not bm25_matches or min_dist > 0.45:
                logger.info(
                    "[Retriever] Min mesafe %.3f > eşik %.3f ve leksikal eşleşme yetersiz → found=False",
                    min_dist,
                    MAX_DISTANCE_THRESHOLD,
                )
                return RetrievalResponse(query=query, hits=[], found=False)
            logger.info(
                "[Retriever] Min mesafe %.3f > eşik %.3f ancak güçlü BM25 eşleşmesi mevcut → hibrit hatta devam ediliyor",
                min_dist,
                MAX_DISTANCE_THRESHOLD,
            )

        # 3. Lexical (Okapi BM25) Arama
        if use_hybrid:
            bm25_hits = self._bm25_engine.search(
                query=query,
                top_k=candidate_count,
                source_filter=source_filter,
                use_expansion=True,
            )
            # RRF Füzyonu (Dense ağırlık=1.0, BM25 ağırlık=0.8)
            fused_candidates = reciprocal_rank_fusion(
                ranked_lists=[(dense_hits, 1.0), (bm25_hits, 0.8)]
            )
        else:
            fused_candidates = dense_hits

        # 4. Kaynak Başına Kota ve Sayfa Çeşitliliği
        if use_source_quota:
            final_hits = apply_source_quota_and_diversity(
                fused_docs=fused_candidates,
                top_k=top_k,
                min_per_source=2,
                max_per_page=2,
                has_source_filter=bool(source_filter),
            )
        else:
            # Standart sayfa tekilleştirme
            seen_pages = {}
            final_hits = []
            for doc in fused_candidates:
                p_key = f"{doc['source_code']}:{doc['doc_page']}"
                if seen_pages.get(p_key, 0) < 2:
                    seen_pages[p_key] = seen_pages.get(p_key, 0) + 1
                    final_hits.append(doc)
                if len(final_hits) >= top_k:
                    break

        # 5. RetrievalResult Listesine Dönüştür
        results = []
        for h in final_hits:
            # BM25'ten gelen ama dense havuzda olmayan öğe için varsayılan distance
            dist = h.get("distance", min_dist + 0.05)
            results.append(
                RetrievalResult(
                    source_code=h["source_code"],
                    display_source=h["display_source"],
                    doc_page=h["doc_page"],
                    heading=h.get("heading", ""),
                    text=h["text"],
                    distance=round(dist, 4),
                    rrf_score=h.get("rrf_score"),
                )
            )

        return RetrievalResponse(query=query, hits=results, found=True)
