"""
Kılavuz Retriever.
Soru → Top-K ilgili chunk.

Kalite Mekanizmaları:
    1. Distance threshold: Eşiğin üzerindeyse "bulunamadı" döner (hallüsinasyon önleme)
    2. Çakışma filtreleme: Aynı sayfadan çok fazla chunk gelirse en yakını tutar
    3. Kaynak filtresi: Opsiyonel — sadece TR2025 veya EG2025'te ara
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rag.config import TOP_K, MAX_DISTANCE_THRESHOLD
from rag.embedder import Embedder
from rag.store import VectorStore


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

    @property
    def similarity_pct(self) -> int:
        """Cosine distance'ı anlaşılır benzerlik yüzdesine çevir."""
        # cosine distance ∈ [0, 2]; 0 = aynı, 2 = zıt
        # similarity = (2 - distance) / 2 × 100
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


# ─── Retriever ────────────────────────────────────────────────────────────────

class Retriever:
    """
    Serbest metin sorusu → ilgili kılavuz bölümleri.

    Kullanım:
        retriever = Retriever(embedder, store)
        response = retriever.retrieve("PASI > 10 ne anlama gelir?")
        print(response.context_text)
    """

    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self._embedder = embedder
        self._store = store

    def retrieve(
        self,
        query: str,
        top_k: int = TOP_K,
        source_filter: Optional[list[str]] = None,
    ) -> RetrievalResponse:
        """
        Sorguyu embed et, ChromaDB'den en yakın chunk'ları çek.

        Args:
            query: Hekimin serbest metin sorusu.
            top_k: Kaç chunk döndürülsün.
            source_filter: ['TR2025'] veya ['EG2025'] veya None (her ikisi).

        Returns:
            RetrievalResponse — hits listesi veya found=False.
        """
        if self._store.is_empty:
            return RetrievalResponse(
                query=query,
                hits=[],
                found=False,
            )

        # Sorguyu embed et (RETRIEVAL_QUERY task type)
        query_vec = self._embedder.embed_query(query)

        # ChromaDB'den sonuçları al
        raw_hits = self._store.query(
            query_embedding=query_vec,
            top_k=top_k + 2,  # Filtreleme sonrası top_k kalması için fazla al
            source_filter=source_filter,
        )

        if not raw_hits:
            return RetrievalResponse(query=query, hits=[], found=False)

        # Distance threshold filtreleme
        filtered = [h for h in raw_hits if h["distance"] <= MAX_DISTANCE_THRESHOLD]

        if not filtered:
            return RetrievalResponse(query=query, hits=[], found=False)

        # Aynı sayfadan çok fazla chunk gelmesin — çeşitlilik için
        filtered = self._deduplicate_by_page(filtered, max_per_page=2)

        # Top-k sınırına kes
        filtered = filtered[:top_k]

        results = [
            RetrievalResult(
                source_code=h["source_code"],
                display_source=h["display_source"],
                doc_page=h["doc_page"],
                heading=h["heading"],
                text=h["text"],
                distance=h["distance"],
            )
            for h in filtered
        ]

        return RetrievalResponse(query=query, hits=results, found=True)

    @staticmethod
    def _deduplicate_by_page(
        hits: list[dict],
        max_per_page: int = 2,
    ) -> list[dict]:
        """
        Aynı sayfa + kaynak kombinasyonundan en fazla max_per_page chunk tut.
        (Zaten distance'a göre sıralı geldiği için en iyi olanlar korunur.)
        """
        seen: dict[str, int] = {}  # "source:page" → count
        result = []
        for h in hits:
            key = f"{h['source_code']}:{h['doc_page']}"
            if seen.get(key, 0) < max_per_page:
                seen[key] = seen.get(key, 0) + 1
                result.append(h)
        return result
