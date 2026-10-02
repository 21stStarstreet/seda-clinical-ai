"""
Klinik Okapi BM25 Arama Motoru.
Dış bağımlılık gerektirmeyen, tıbbi varlıkları (ilaç isimleri, dozlar, skorlar)
tam metin (lexical) eşleştirmesi ile yüksek hızda bulan BM25 motoru.
"""

from __future__ import annotations

import math
import re
import logging
from collections import Counter
from typing import List, Dict, Optional, Tuple

from rag.store import VectorStore
from rag.bilingual_dictionary import expand_query_bilingual

logger = logging.getLogger(__name__)


# ─── Klinik Metin Tokenizer'ı ──────────────────────────────────────────────────

def tokenize_clinical_text(text: str) -> List[str]:
    """
    Tıbbi terimleri, tireli bileşikleri ve sayısal klinik eşikleri koruyan tokenizer.
    Örnekler:
        'Anti-TNF IL-17 PASI>10' → ['anti-tnf', 'il-17', 'pasi', '10']
    """
    if not text:
        return []

    # Türkçe karakter duyarlı küçük harfe çevirme
    text = (
        text.replace("İ", "i")
        .replace("I", "ı")
        .lower()
    )

    # Tireli tıbbi bileşikler veya alfanümerik kelimeler
    tokens = re.findall(r"[a-z0-9çğıöşü]+(?:-[a-z0-9çğıöşü]+)*", text)
    return tokens


# ─── Okapi BM25 Algoritması ───────────────────────────────────────────────────

class BM25Okapi:
    """
    Standart Okapi BM25 sıralama algoritması (k1=1.5, b=0.75).
    """

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avgdl = (
            sum(len(doc) for doc in corpus) / self.corpus_size
            if self.corpus_size > 0
            else 0.0
        )
        self.doc_freqs: List[Counter[str]] = []
        self.nd: Dict[str, int] = {}

        for doc in corpus:
            freqs = Counter(doc)
            self.doc_freqs.append(freqs)
            for word in freqs:
                self.nd[word] = self.nd.get(word, 0) + 1

        # Inverse Document Frequency (IDF) hesaplama
        self.idf: Dict[str, float] = {}
        for word, freq in self.nd.items():
            self.idf[word] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query_tokens: List[str]) -> List[float]:
        """Sorgu token'larının tüm dokümanlar üzerindeki BM25 skorunu döner."""
        scores = [0.0] * self.corpus_size
        for q in query_tokens:
            if q not in self.idf:
                continue
            idf_q = self.idf[q]
            for i, freqs in enumerate(self.doc_freqs):
                if q in freqs:
                    tf = freqs[q]
                    doc_len = sum(freqs.values())
                    denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                    scores[i] += idf_q * (tf * (self.k1 + 1.0)) / denom
        return scores


# ─── BM25 Koleksiyon Arama Servisi ───────────────────────────────────────────

class BM25SearchEngine:
    """
    ChromaDB chunk'larını in-memory indeksleyen ve BM25 araması sağlayan servis.
    """

    _instance: Optional["BM25SearchEngine"] = None

    def __init__(self, store: VectorStore) -> None:
        self._store = store
        self._documents: List[dict] = []
        self._bm25: Optional[BM25Okapi] = None
        self._build_index()

    @classmethod
    def get_instance(cls, store: VectorStore) -> "BM25SearchEngine":
        """Singleton erişimi."""
        if cls._instance is None:
            cls._instance = cls(store)
        return cls._instance

    def _build_index(self) -> None:
        """ChromaDB'deki tüm chunk'ları çekip BM25 indeksini oluşturur."""
        col = self._store._collection
        total = col.count()
        if total == 0:
            logger.warning("[BM25] Koleksiyon boş, indeks oluşturulamadı.")
            return

        res = col.get(include=["metadatas", "documents"])
        metas = res.get("metadatas", [])
        docs = res.get("documents", [])

        tokenized_corpus: List[List[str]] = []
        self._documents = []

        for m, d in zip(metas, docs):
            heading = m.get("heading", "")
            combined_text = f"{heading} {d}"
            tokens = tokenize_clinical_text(combined_text)
            tokenized_corpus.append(tokens)

            self._documents.append({
                "source_code": m.get("source_code", ""),
                "display_source": m.get("display_source", ""),
                "doc_page": m.get("doc_page", 1),
                "heading": heading,
                "text": d,
            })

        self._bm25 = BM25Okapi(tokenized_corpus)
        logger.info("[BM25] %d adet kılavuz chunk'ı başarıyla indekslendi.", len(self._documents))

    def search(
        self,
        query: str,
        top_k: int = 20,
        source_filter: Optional[List[str]] = None,
        use_expansion: bool = True,
    ) -> List[dict]:
        """
        Sorgu için BM25 ile en alakalı dokümanları bulur.
        """
        if self._bm25 is None or not self._documents:
            return []

        # İki dilli terim genişletmesi
        expanded_query = expand_query_bilingual(query) if use_expansion else query
        query_tokens = tokenize_clinical_text(expanded_query)

        scores = self._bm25.get_scores(query_tokens)

        # Filtreleme ve sıralama
        scored_docs: List[Tuple[int, float]] = []
        for idx, score in enumerate(scores):
            if score <= 0.0:
                continue
            doc = self._documents[idx]
            if source_filter and doc["source_code"] not in source_filter:
                continue
            scored_docs.append((idx, score))

        scored_docs.sort(key=lambda x: x[1], reverse=True)
        top_items = scored_docs[:top_k]

        results = []
        for idx, score in top_items:
            doc = self._documents[idx].copy()
            doc["bm25_score"] = round(score, 4)
            results.append(doc)

        return results
