"""
PDF Metin Çıkarıcı.
pdfplumber ile PDF → temiz sayfa metni + metadata.

Tasarım Kararları:
    - pdfplumber seçildi çünkü kelime düzeyinde font boyutu bilgisi veriyor
      → büyük/kalın metin = bölüm başlığı tespiti
    - Her sayfa için header/footer kalıpları temizlenir (kaynak bazında)
    - Çok az metin içeren sayfalar (grafik, şekil) atlanır
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pdfplumber

from rag.config import SOURCES, MIN_CHUNK_WORDS


# ─── Veri Yapıları ────────────────────────────────────────────────────────────

@dataclass
class PageData:
    """Tek bir PDF sayfasının temizlenmiş içeriği."""

    source_code: str
    """Kaynak kodu: 'TR2025' veya 'EG2025'"""

    pdf_index: int
    """PDF içindeki 0 tabanlı sayfa indeksi."""

    doc_page: int
    """Döküman görünen sayfa numarası (PDF içeriğinden tespit edilir)."""

    heading: str
    """Sayfanın en olası bölüm başlığı (heuristic)."""

    text: str
    """Temizlenmiş ham metin."""

    word_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.word_count = len(self.text.split())


# ─── Kaynak Bazlı Temizleme Kalıpları ────────────────────────────────────────

_NOISE_PATTERNS: dict[str, list[str]] = {
    "TR2025": [
        r"www\.psokid\.org\s*",
        r"Türkiye\s+Psoriasis\s+Tedavi\s+Kılavuzu\s*[-–]\s*202[0-9]\s*",
        r"^\s*\d{1,3}\s*$",
        r"^psokid\.org\s*",
    ],
    "EG2025": [
        r"EUROGUIDERM\s+GUIDELINE\s+FOR\s+THE\b.*",
        r"EUROGUIDEREM\s+GUIDELINE.*",
        r"TREATMENT\s+OF\s+PSORIASIS\s+VULGARIS.*",
        r"CC\s+BY\s+NC\s+©\s+EDF[^\n]*",
        r"©\s*EDF[^\n]*",
        r"^\s*\d{1,3}\s*$",
    ],
}

_COMPILED: dict[str, list[re.Pattern]] = {
    src: [re.compile(p, re.MULTILINE | re.IGNORECASE)
          for p in patterns]
    for src, patterns in _NOISE_PATTERNS.items()
}


def _clean_text(text: str, source_code: str) -> str:
    """Kaynak bazlı header/footer kalıplarını temizle."""
    for pattern in _COMPILED.get(source_code, []):
        text = pattern.sub("", text)
    # Üçten fazla ardışık boş satırı iki'ye indir
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Satır başı / sonundaki fazla boşlukları temizle
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(lines).strip()


def _detect_page_number(text: str, pdf_index: int) -> int:
    """
    PDF içeriğindeki görünen sayfa numarasını bul.
    Fallback: pdf_index + 1
    """
    # Satırların başında tek başına duran sayılar → sayfa no adayı
    for line in text.splitlines()[:6]:  # ilk 6 satır
        stripped = line.strip()
        if stripped.isdigit():
            num = int(stripped)
            # Makul sayfa aralığında mı? (PDF boyutunun %150'si kadar)
            if 1 <= num <= 900:
                return num
    return pdf_index + 1


def _detect_heading(page: "pdfplumber.page.Page", source_code: str) -> str:
    """
    Sayfadaki en büyük font boyutlu kısa satırı bölüm başlığı olarak tespit et.
    Font bilgisi yoksa ALL CAPS kısa satır heuristic'i kullan.
    """
    try:
        # pdfplumber kelime düzeyinde font boyutu verir
        words = page.extract_words(
            x_tolerance=2,
            y_tolerance=3,
            extra_attrs=["size", "fontname"],
        )
        if not words:
            return ""

        # Medyan font boyutunu hesapla
        sizes = [w.get("size", 10) or 10 for w in words]
        sizes_sorted = sorted(sizes)
        median_size = sizes_sorted[len(sizes_sorted) // 2]

        # Medyanın %130'undan büyük fontlu kelimeler → başlık adayı
        heading_threshold = median_size * 1.30

        # Aynı dikeydeki (y koordinatı) büyük fontlu kelimeleri grupla
        heading_lines: dict[int, list[str]] = {}
        for w in words:
            if (w.get("size") or 0) >= heading_threshold:
                y_key = round(w.get("top", 0) / 5) * 5  # 5px tolerans
                heading_lines.setdefault(y_key, []).append(w.get("text", ""))

        if heading_lines:
            # En üstteki (küçük y değerli) başlık satırını al
            top_y = min(heading_lines.keys())
            candidate = " ".join(heading_lines[top_y]).strip()
            # Çok uzun veya çok kısa değilse kullan
            if 3 <= len(candidate) <= 120:
                return candidate

    except Exception:
        pass  # pdfplumber bazı sayfalarda hata verebilir

    # Fallback: ilk 10 satırdan ALL CAPS veya başlık görünümlü satır
    text = page.extract_text() or ""
    for line in text.splitlines()[:10]:
        s = line.strip()
        if not s or len(s) < 3 or len(s) > 100:
            continue
        # Kılavuz başlık formatları: büyük harf ağırlıklı, nokta yok
        upper_ratio = sum(1 for c in s if c.isupper()) / max(len(s), 1)
        if upper_ratio > 0.6 and not s.endswith("."):
            return s

    return ""


# ─── Ana Çıkarıcı ─────────────────────────────────────────────────────────────

class PDFExtractor:
    """
    PDF dosyasından sayfa bazlı temizlenmiş metin ve metadata üretir.
    Her çağrıda generator döner — bellek tasarrufu için.
    """

    def extract_source(self, source_code: str) -> Iterator[PageData]:
        """
        Verilen kaynak kodu için tüm sayfaları çıkarır.

        Args:
            source_code: 'TR2025' veya 'EG2025'

        Yields:
            Her kullanılabilir sayfa için bir PageData nesnesi.
        """
        cfg = SOURCES.get(source_code)
        if cfg is None:
            raise ValueError(f"Bilinmeyen kaynak kodu: {source_code}")

        pdf_path = Path(cfg["path"])
        if not pdf_path.exists():
            raise FileNotFoundError(
                f"PDF bulunamadı: {pdf_path}\n"
                f"docs/guidelines/ klasöründe '{pdf_path.name}' dosyası olmalı."
            )

        with pdfplumber.open(str(pdf_path)) as pdf:
            total = len(pdf.pages)
            print(f"  [{source_code}] {total} sayfa işleniyor...")

            for idx, page in enumerate(pdf.pages):
                raw_text = page.extract_text() or ""
                cleaned = _clean_text(raw_text, source_code)

                # Yeterli metin içermeyen sayfaları atla
                word_count = len(cleaned.split())
                if word_count < MIN_CHUNK_WORDS:
                    continue

                doc_page = _detect_page_number(cleaned, idx)
                heading = _detect_heading(page, source_code)

                yield PageData(
                    source_code=source_code,
                    pdf_index=idx,
                    doc_page=doc_page,
                    heading=heading,
                    text=cleaned,
                )

    def extract_all(self) -> Iterator[PageData]:
        """Tüm kayıtlı kaynaklar için PageData üretir."""
        for source_code in SOURCES:
            try:
                yield from self.extract_source(source_code)
            except FileNotFoundError as exc:
                print(f"  ⚠️  {exc}")
            except Exception as exc:
                print(f"  ❌  [{source_code}] Hata: {exc}")
