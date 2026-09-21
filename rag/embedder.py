"""
Gemini Embedding Wrapper.
Chunk metinlerini vektörlere (768 boyutlu) dönüştürür.

Teknik Notlar:
    - text-embedding-004: Google'ın en güncel çokdilli embedding modeli
    - Türkçe (TR2025) ve İngilizce (EG2025) aynı vektör uzayında temsil edilir
    - Batch işlem: 50 metin / request → API rate limit'e saygılı
    - Retry: Geçici hatalarda 3 deneme, üstel bekleme
"""

from __future__ import annotations

import time
import logging
from typing import Sequence

import google.generativeai as genai

from rag.config import (
    EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DELAY_SEC,
    TASK_TYPE_INDEX,
    TASK_TYPE_QUERY,
)
from config.settings import settings

logger = logging.getLogger(__name__)


class Embedder:
    """
    Gemini text-embedding-004 ile metin → vektör dönüşümü.

    Kullanım:
        embedder = Embedder()
        vectors = embedder.embed_documents(["metin 1", "metin 2"])
        query_vec = embedder.embed_query("PASI eşiği nedir?")
    """

    def __init__(self) -> None:
        api_key = settings.gemini_api_key
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY ortam değişkeni ayarlanmamış. "
                ".env dosyasını kontrol edin."
            )
        genai.configure(api_key=api_key)
        self._model = EMBEDDING_MODEL
        logger.info("[Embedder] Gemini %s hazır.", self._model)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Belge embedding'leri üret (indexleme için).
        Batch işlem ve rate limiting içerir.

        Args:
            texts: Embed edilecek metin listesi.

        Returns:
            Her metne karşılık gelen vektör listesi.
        """
        all_vectors: list[list[float]] = []
        total = len(texts)

        for batch_start in range(0, total, EMBEDDING_BATCH_SIZE):
            batch = texts[batch_start: batch_start + EMBEDDING_BATCH_SIZE]
            batch_end = min(batch_start + EMBEDDING_BATCH_SIZE, total)

            vectors = self._embed_with_retry(batch, task_type=TASK_TYPE_INDEX)
            all_vectors.extend(vectors)

            print(
                f"  Embedding: {batch_end}/{total} "
                f"({batch_end/total*100:.0f}%)",
                end="\r",
            )

            # Rate limiting — sadece batch aralarında bekle
            if batch_end < total:
                time.sleep(EMBEDDING_DELAY_SEC)

        print()  # newline after \r progress
        return all_vectors

    def embed_query(self, text: str) -> list[float]:
        """
        Tek sorgu embedding'i üret (retrieval için).
        RETRIEVAL_QUERY task type kullanılır — indexlemeden farklı.
        """
        vectors = self._embed_with_retry([text], task_type=TASK_TYPE_QUERY)
        return vectors[0]

    def _embed_with_retry(
        self,
        texts: list[str],
        task_type: str,
        max_retries: int = 6,
    ) -> list[list[float]]:
        """
        Üstel ve kota duyarlı bekleme ile retry mantığı.
        429 Rate limit veya geçici API hatalarında adaptif bekler.
        """
        for attempt in range(max_retries):
            try:
                result = genai.embed_content(
                    model=self._model,
                    content=texts,
                    task_type=task_type,
                )
                embeddings = result.get("embedding", [])

                # Tek metin gönderildiğinde API bazen liste değil dict döner
                if embeddings and isinstance(embeddings[0], (int, float)):
                    embeddings = [embeddings]

                return embeddings  # type: ignore[return-value]

            except Exception as exc:
                err_str = str(exc).lower()
                is_quota = "429" in err_str or "quota" in err_str or "exhausted" in err_str

                if is_quota:
                    wait = 15 + (attempt * 10)  # 15s, 25s, 35s, 45s...
                else:
                    wait = 2 ** attempt

                if attempt < max_retries - 1:
                    print(
                        f"\n  ⚠️ [Embedder] API uyarısı ({'Kota/RateLimit' if is_quota else 'Hata'}), "
                        f"{wait}s beklenip tekrar denenecek (deneme {attempt + 1}/{max_retries})...",
                        flush=True,
                    )
                    time.sleep(wait)
                else:
                    logger.error("[Embedder] Tüm denemeler başarısız: %s", exc)
                    raise

        return []  # mypy için (ulaşılamaz)
