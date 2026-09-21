"""
Metin Parçalayıcı (Chunker).
Sayfa metinlerini anlam kaybı olmadan küçük, örtüşen parçalara böler.

Tasarım Kararı — Neden bu strateji?
    Sabit karakter bölümü (naif yaklaşım) paragraf ortasında keser.
    Cümle bazlı bölüm ise bazen çok küçük çok büyük chunk üretir.
    Kelime bazlı örtüşmeli pencere (bu yaklaşım):
      - Paragraf sınırlarına saygı duyar (önce \n\n ile böler)
      - Pencere boyutu aşılıyorsa cümle bazında ince ayar yapar
      - Örtüşme → ardışık chunk'lar arasında bağlam sürekliliği
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rag.config import CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS, MIN_CHUNK_WORDS
from rag.extractor import PageData


# ─── Veri Yapısı ─────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    """Tek bir metin parçası ve tam metadata'sı."""

    chunk_id: str
    """Unique ID: '{source_code}_p{doc_page}_c{chunk_index}'"""

    source_code: str
    heading: str
    doc_page: int
    text: str
    word_count: int

    @property
    def display_source(self) -> str:
        """API yanıtında görünecek kısa kaynak etiketi."""
        from rag.config import SOURCES
        return SOURCES.get(self.source_code, {}).get("display_name", self.source_code)


# ─── Yardımcılar ─────────────────────────────────────────────────────────────

def _split_into_words(text: str) -> list[str]:
    """Metni kelimeler listesine çevir, boşlukları koru."""
    return text.split()


def _words_to_text(words: list[str]) -> str:
    return " ".join(words)


def _split_by_paragraphs(text: str) -> list[str]:
    """Çift satır sonu ile paragraf bazında böl, boşları atla."""
    parts = re.split(r"\n\n+", text)
    return [p.strip() for p in parts if p.strip()]


# ─── Ana Parçalayıcı ──────────────────────────────────────────────────────────

class Chunker:
    """
    PageData listesini Chunk listesine dönüştürür.

    Algoritma:
    1. Her sayfanın metnini paragraflara böl.
    2. Paragrafları sırayla bir pencereye ekle.
    3. Pencere CHUNK_SIZE_WORDS'ü aşınca bir chunk kaydet,
       son CHUNK_OVERLAP_WORDS kelimeyle yeni pencereye başla.
    4. Sayfa sonu, örtüşmeyi sıfırlamaz — bağlam sürekliliği için.
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE_WORDS,
        overlap: int = CHUNK_OVERLAP_WORDS,
        min_words: int = MIN_CHUNK_WORDS,
    ) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_words = min_words

    def chunk_pages(self, pages: list[PageData]) -> list[Chunk]:
        """
        Sayfa listesini chunk listesine dönüştür.
        Sayfa meta verisi (sayfa no, başlık) her chunk'a atanır.
        """
        chunks: list[Chunk] = []

        # Kaynak bazında ayrı işle — kaynaklar arası karışma istemiyoruz
        from itertools import groupby
        from operator import attrgetter

        for source_code, group in groupby(pages, key=attrgetter("source_code")):
            source_chunks = self._chunk_source(list(group))
            chunks.extend(source_chunks)

        return chunks

    def _chunk_source(self, pages: list[PageData]) -> list[Chunk]:
        chunks: list[Chunk] = []
        chunk_index = 0

        # Kayan pencere
        window_words: list[str] = []
        window_page: int = pages[0].doc_page if pages else 1
        window_heading: str = pages[0].heading if pages else ""
        source_code = pages[0].source_code if pages else "UNKNOWN"

        def _flush(words: list[str], page: int, heading: str) -> None:
            nonlocal chunk_index
            if len(words) < self.min_words:
                return
            text = _words_to_text(words)
            chunks.append(Chunk(
                chunk_id=f"{source_code}_p{page}_c{chunk_index}",
                source_code=source_code,
                heading=heading,
                doc_page=page,
                text=text,
                word_count=len(words),
            ))
            chunk_index += 1

        for page in pages:
            paragraphs = _split_by_paragraphs(page.text)

            for para in paragraphs:
                para_words = _split_into_words(para)

                for word in para_words:
                    window_words.append(word)

                    if len(window_words) >= self.chunk_size:
                        # Chunk'ı kaydet
                        _flush(window_words[:], window_page, window_heading)
                        # Örtüşme: son N kelimeyle yeni pencere başlat
                        window_words = window_words[-self.overlap:]
                        # Pencere geçerli sayfanın bağlamına geçiyor
                        window_page = page.doc_page
                        window_heading = page.heading

            # Sayfa bitince heading güncelle (sonraki pencere için)
            if page.heading:
                window_heading = page.heading
            window_page = page.doc_page

        # Son pencereyi de kaydet
        _flush(window_words, window_page, window_heading)

        return chunks
