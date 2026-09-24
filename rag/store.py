"""
ChromaDB Koleksiyon Yönetimi.
Chunk'ları vektör veritabanına yazar ve geri okur.

Tek Koleksiyon Kararı:
    İki ayrı koleksiyon (TR2025 / EG2025) yerine tek koleksiyon tercih edildi.
    Neden? Hekim "sadece Türkiye kılavuzunda ara" diyebilir — metadata filter ile bu
    kolayca yapılır. Ayrıca çapraz-kaynak retrieval (her ikisinden sonuç) de aynı
    sorguda çalışır. İki ayrı koleksiyon gereksiz complexity yaratır.
"""

from __future__ import annotations

import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from rag.config import CHROMA_DB_PATH, COLLECTION_NAME
from rag.chunker import Chunk

logger = logging.getLogger(__name__)

# ChromaDB'nin kendi telemetry/log baskısı
import os
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


class VectorStore:
    """
    ChromaDB kalıcı koleksiyon wrapper'ı.

    Özellikler:
        - İlk çağrıda koleksiyon oluşturulur, sonraki çağrılarda mevcut açılır
        - Cosine distance kullanılır (L2 yerine — metin benzerliği için daha iyi)
        - Her chunk: id, embedding, metin, metadata (kaynak, sayfa, başlık)
    """

    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # cosine distance
        )
        logger.info(
            "[VectorStore] Koleksiyon '%s' açıldı. Mevcut chunk: %d",
            COLLECTION_NAME,
            self._collection.count(),
        )

    @property
    def chunk_count(self) -> int:
        """Koleksiyondaki toplam chunk sayısı."""
        return self._collection.count()

    @property
    def is_empty(self) -> bool:
        return self.chunk_count == 0

    def add_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """
        Chunk ve embedding'lerini koleksiyona ekle.
        Mevcut chunk ID'si varsa üzerine yaz (upsert).
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunk sayısı ({len(chunks)}) ile embedding sayısı "
                f"({len(embeddings)}) eşleşmiyor."
            )

        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "source_code": c.source_code,
                    "display_source": c.display_source,
                    "doc_page": c.doc_page,
                    "heading": c.heading or "",
                }
                for c in chunks
            ],
        )
        logger.debug("[VectorStore] %d chunk eklendi/güncellendi.", len(chunks))

    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        source_filter: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Sorgu vektörüne en yakın chunk'ları döndür.

        Args:
            query_embedding: Embed edilmiş sorgu vektörü.
            top_k: Kaç sonuç isteniyor.
            source_filter: Kısıtlanacak kaynak kodları ['TR2025'] gibi.

        Returns:
            Sıralı sonuç listesi. Her öğe:
            {'id', 'text', 'distance', 'source_code', 'doc_page', 'heading', 'display_source'}
        """
        where = None
        if source_filter and len(source_filter) == 1:
            where = {"source_code": {"$in": source_filter}}
        elif source_filter and len(source_filter) > 1:
            where = {"source_code": {"$in": source_filter}}

        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.chunk_count),
            where=where,
            include=["documents", "distances", "metadatas"],
        )

        if not result["ids"] or not result["ids"][0]:
            return []

        hits = []
        for idx in range(len(result["ids"][0])):
            meta = result["metadatas"][0][idx] if result["metadatas"] else {}
            hits.append({
                "id": result["ids"][0][idx],
                "text": result["documents"][0][idx] if result["documents"] else "",
                "distance": result["distances"][0][idx] if result["distances"] else 1.0,
                "source_code": meta.get("source_code", ""),
                "display_source": meta.get("display_source", ""),
                "doc_page": meta.get("doc_page", 0),
                "heading": meta.get("heading", ""),
            })

        return hits

    def reset(self) -> None:
        """Koleksiyonu tamamen sıfırla (yeniden indexleme için)."""
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("[VectorStore] Koleksiyon sıfırlandı.")

    def chunk_count_by_source(self, source_code: str) -> int:
        """
        Verilen kaynak koduna ait chunk sayısını döndür.

        Artımlı indexleme için kritik: hangi kaynakların zaten
        indekslendiğini ve hangilerinin eksik olduğunu anlamak için kullanılır.
        """
        try:
            result = self._collection.get(
                where={"source_code": {"$eq": source_code}},
                include=[],  # Sadece sayımı istiyoruz — vektör/metin yok
            )
            return len(result["ids"])
        except Exception as exc:
            logger.warning("[VectorStore] chunk_count_by_source hatası: %s", exc)
            return 0

    def delete_by_source(self, source_code: str) -> int:
        """
        Verilen kaynak koduna ait tüm chunk'ları sil.

        Kullanım: --force --source EG2025 ile sadece EG2025'i
        silip yeniden indekslemek için. TR2025'e dokunulmaz.

        Returns:
            Silinen chunk sayısı.
        """
        try:
            # Önce silinecek ID'leri al (ChromaDB delete where-only destekler ama
            # count bilgisi için önce get gerekiyor)
            existing = self._collection.get(
                where={"source_code": {"$eq": source_code}},
                include=[],
            )
            ids_to_delete = existing["ids"]
            if not ids_to_delete:
                logger.info("[VectorStore] Silinecek '%s' chunk'ı bulunamadı.", source_code)
                return 0

            self._collection.delete(ids=ids_to_delete)
            logger.info("[VectorStore] %d '%s' chunk'ı silindi.", len(ids_to_delete), source_code)
            return len(ids_to_delete)
        except Exception as exc:
            logger.error("[VectorStore] delete_by_source hatası: %s", exc)
            raise

    def indexed_sources(self) -> dict[str, int]:
        """
        Koleksiyondaki her kaynak kodunun chunk sayısını döndür.
        Artımlı indexleme durumu raporu için kullanılır.

        Returns:
            {"TR2025": 265, "EG2025": 0} gibi bir sözlük.
        """
        from rag.config import SOURCES
        return {
            src: self.chunk_count_by_source(src)
            for src in SOURCES
        }

    def get_existing_chunk_ids(self, source_code: str) -> set[str]:
        """
        Verilen kaynak koduna ait koleksiyondaki mevcut chunk ID'lerini küme olarak döndür.
        Checkpointing / Resume mantığı için kullanılır.
        """
        try:
            result = self._collection.get(
                where={"source_code": {"$eq": source_code}},
                include=[],
            )
            return set(result["ids"]) if result and "ids" in result else set()
        except Exception as exc:
            logger.warning("[VectorStore] get_existing_chunk_ids hatası: %s", exc)
            return set()


