"""
Sorgu Ön İşleyici (Query Preprocessor) — Two-Stage RAG Katman 1.

Amaç:
    Ham hekimin sorusunu ChromaDB'nin anlayabileceği zenginleştirilmiş
    tıbbi terminoloji ile yeniden yaz.

Mimari Kararlar:
    1. Bu modül tamamen bağımsız çalışır — RAG pipeline'ının geri kalanına
       bağımlılığı yoktur. Test edilebilir, izole edilebilir.

    2. Üç katmanlı strateji (maliyetten ucuza doğru sıralı):
       a) Kural tabanlı kısaltma genişletme — 0ms, 0 API maliyeti
       b) Devam sorusu tespiti + bağlam füzyonu — 0ms, 0 API maliyeti
       c) gemini-3.5-flash-lite reformülasyon — ~80ms, düşük kota

    3. Graceful degradation: LLM çağrısı başarısız olursa
       kısaltma genişletilmiş sorgu kullanılır, sistem durmaz.

    4. Orijinal sorgu korunur: Preprocessor SADECE retrieval sorgusunu
       değiştirir. QA engine'e her zaman orijinal soru iletilir.
       (Hekimin sorusunu bozmamak için)

Tetiklenme Mantığı:
    LLM reformülasyonu YALNIZCA aşağıdaki koşullarda tetiklenir:
    - Koşul A: Soru kısa (≤8 kelime) VE tıbbi terim içermiyor
    - Koşul B: Devam sorusu göstergesi var VE önceki AI yanıtı mevcut
    Aksi halde kısaltma genişletme sonucu doğrudan kullanılır.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import google.generativeai as genai

from rag.config import PREPROCESSOR_MODEL, PREPROCESSOR_MAX_TOKENS, PREPROCESSOR_TIMEOUT_SEC
from config.settings import settings

logger = logging.getLogger(__name__)


# ─── Tıbbi Kısaltma Sözlüğü ─────────────────────────────────────────────────
# Kural: Sadece kılavuz metinlerinde geçen ifadelerle eşleştir.
# Yanlış eşleşme riski olan genel kısaltmalar eklenmez.
MEDICAL_ABBREVIATIONS: dict[str, str] = {
    # Branşlar ve Birimler
    "ftr":     "Fiziksel Tıp ve Rehabilitasyon (FTR)",
    "ftr'ye":  "Fiziksel Tıp ve Rehabilitasyon (FTR) birimine",
    "ftr'de":  "Fiziksel Tıp ve Rehabilitasyon (FTR) biriminde",
    "ftr'nin": "Fiziksel Tıp ve Rehabilitasyon (FTR) biriminin",
    "ftr'a":   "Fiziksel Tıp ve Rehabilitasyon (FTR) birimine",
    "romato":  "Romatoloji",

    # Tanı ve Hastalıklar
    "psa":      "Psoriatik Artrit (PsA)",
    "psa'lı":   "Psoriatik Artrit (PsA) olan",
    "psa'da":   "Psoriatik Artritte",
    "pso":      "Psoriasis",
    "psor":     "Psoriasis",

    # Tedavi ve İlaçlar
    # Not: Daha uzun eşleşmeler (biyosimiyer) kısa olanlardan (biyosi) önce gelir —
    # böylece "biyosi" → "biyolojik ilaç (biyosimiyer...)" genişletildikten sonra
    # "biyolojik" kelimesi tekrar eşleştirilmez.
    "biyosi":   "biyolojik ilaç (biyosimiyer veya orijinal biyolojik ajan)",
    "mtz":      "metotreksat",
    "mtx":      "metotreksat",
    "ssa":      "siklosporin",
    "acit":     "asitretin",
    "tnf":      "TNF-alfa inhibitörü (anti-TNF)",
    "anti-tnf": "TNF-alfa inhibitörü",
    "il17":     "IL-17 inhibitörü (anti-IL-17)",
    "il23":     "IL-23 inhibitörü (anti-IL-23)",
    "jak":      "JAK inhibitörü",
    "seku":     "sekukinumab",
    "ixe":      "ixekizumab",
    "bime":     "bimekizumab",
    "guse":     "guselkumab",
    "rise":     "risankizumab",
    "uste":     "ustekinumab",
    "adali":    "adalimumab",
    "etaner":   "etanersept",

    # Skorlar ve Ölçekler
    "pasi":     "PASI (Psoriasis Area Severity Index)",
    "dlqi":     "DLQI (Dermatology Life Quality Index)",
    "dyqi":     "DLQI (Dermatology Life Quality Index)",
    "dyki":     "DLQI (Dermatology Life Quality Index)",
    "bsa":      "BSA (Vücut Yüzey Alanı — Body Surface Area)",
    "vki":      "VKİ (Vücut Kitle İndeksi)",
    "ldl":      "LDL kolesterol",

    # Genel Klinik
    "hiv":      "HIV",
    "tbc":      "tüberküloz (TBC)",
    "tb":       "tüberküloz",
    "ana":      "antinükleer antikor (ANA)",
    "hbsag":    "Hepatit B yüzey antijeni (HBsAg)",
    "anc":      "absolü nötrofil sayısı (ANC)",
    "kvk":      "kardiyovasküler",
}

# ─── Devam Sorusu Göstergeleri ────────────────────────────────────────────────
# Bu kelimeler başında/içinde geçen kısa sorgular büyük ihtimalle
# önceki soruya atıfta bulunuyor.
CONTINUATION_KEYWORDS: frozenset[str] = frozenset({
    "tamam da", "peki", "yani", "bunun", "bunu", "buna", "bunlar",
    "bunları", "bunlara", "oraya", "orada", "oradan", "ona", "onun",
    "orada", "onu", "onları", "bu durumda", "bu konuda",
    "bu hastada", "o zaman", "ee peki", "ya da", "ya peki",
    "devamında", "sonrasında", "ondan sonra",
})

# ─── Tıbbi Terim Desenleri ────────────────────────────────────────────────────
# Eğer sorguda bu desenler varsa zaten tıbbi terminoloji kullanılmış →
# LLM reformülasyonuna gerek yok.
_MEDICAL_TERM_PATTERN = re.compile(
    r"\b(pasi|dlqi|bsa|vki|ldl|psoriasis|psoriatik|biyolojik|metotreksat|"
    r"siklosporin|asitretin|romatoloji|dermatoloji|anti.?tnf|anti.?il|"
    r"sistemik|topikal|biyosimiyer|sekukinumab|ixekizumab|guselkumab|"
    r"ustekinumab|adalimumab|etanersept|risankizumab|bimekizumab|"
    r"jak inhibit|indüksiyon|idame|kılavuz|sevk kriterleri|tedavi basamağı)\b",
    re.IGNORECASE,
)

# ─── Klinik Dışı Girdi Tespiti ────────────────────────────────────────────────
# Bu regex'ler anlamlı alfanümerik Türkçe/İngilizce kelime içermeyen veya
# açıkça klinik bağlamla ilgisiz girdileri yakalar.
# Amaç: Preprocessor'dan ÖNCE filtrele — LLM'e asla ulaşmasın.

# Yalnızca tekrarlayan karakter grupları: "haha", "ahahah", "hehehe", "hı hı", "ahahaha"
_LAUGHTER_PATTERN = re.compile(
    r"^[\s!?.]*(?:(?:a*h+a*)+|(?:he)+|(?:hı)+|hee+|hey|hi+|ho+|(?:ah)+|eh+|ih+|öh+|uh+|hihi|hehe)+[\s!?.]*$",
    re.IGNORECASE | re.UNICODE,
)

# Yalnızca noktalama, boşluk, emoji gibi içerik: "!!!", "???", "...", ":)", ":D"
_PUNCTUATION_ONLY_PATTERN = re.compile(
    r"^[^\w\u00C0-\u024F\u0100-\u024F\u011E\u011F\u015E\u015F\u0130\u0131\u00D6\u00F6\u00DC\u00FC\u00C7\u00E7]{1,}$",
    re.UNICODE,
)

# Anlamlı en az 3 karakter uzunluğunda kelime içermiyor mu?
_MIN_WORD_LENGTH = 3  # Bu uzunluktan kısa tüm kelimeleri içeren girdi reddedilir
_MIN_REAL_WORD_COUNT = 1  # En az 1 adet ≥3 karakter Türkçe/Latin kelime beklenir

# ─── Genel Klinik Anahtar Kelime Tabanı ──────────────────────────────────────
# Tıbbi olmayan ama klinik bağlam içeren genel Türkçe kelimeler
_GENERAL_CLINICAL_WORDS = frozenset({
    "tedavi", "hastalık", "hasta", "doktor", "hekim", "ilaç", "kılavuz",
    "sevk", "muayene", "tanı", "belirtisi", "semptom", "sonuç", "rapor",
    "takip", "kontrol", "doz", "başlanır", "başlanmalı", "verilir", "önerilir",
    "tarama", "test", "laboratuvar", "kan", "değer", "düzey", "yüksek", "düşük",
    "artrit", "eklem", "deri", "cilt", "lezyon", "plak", "yama", "ağrı",
    "kaşıntı", "yangı", "enfeksiyon", "yan etki", "risk", "kriter",
})

# Tek başına klinik bağlamı olmayan sosyal/gündelik kelimeler
_SOCIAL_ONLY_WORDS: frozenset[str] = frozenset({
    "merhaba", "selam", "günaydın", "iyi", "akşamlar", "geceler",
    "tamam", "tamamdır", "harika", "süper", "bravo",
    "teşekkür", "teşekkürler", "sağol", "eyvallah", "evet", "hayır",
    "nope", "yep", "ok", "okay", "cool", "nice", "wow",
    "lol", "omg", "xd",
})


def _is_non_clinical_input(soru: str) -> bool:
    """
    Girdinin klinik bir soru olup olmadığını hızlıca kontrol et.

    Klinik OLMAYAN girdi örnekleri: "Haha!", "!!!", "ok", "tamam", ":D", "hehe"
    Klinik girdi örnekleri: "pasi nedir?", "tamam da ftr ne zaman?", "ok ama metotreksat dozu?"

    Mantık:
        1. Gülen/anlamsız ses taklitleri → klinik değil
        2. Sadece noktalama → klinik değil
        3. 3+ karakterli en az 1 gerçek kelime yoksa → klinik değil
        4. Sohbet geçmişi bağlamında bile tek başına anlamsız → LLM'e bırakmadan filtrele
    """
    soru_stripped = soru.strip()

    # 1. Tamamen boş veya çok kısa
    if len(soru_stripped) < 2:
        return True

    # 2. Gülen ses taklidleri: haha, hehe, hıhı, ahahah vb.
    if _LAUGHTER_PATTERN.match(soru_stripped):
        return True

    # 3. Sadece noktalama/sembol
    if _PUNCTUATION_ONLY_PATTERN.match(soru_stripped):
        return True

    # 4. En az 1 adet ≥3 karakter gerçek kelime var mı?
    # (Türkçe harf karakterleri dahil)
    words = re.findall(r"[a-zA-ZğüşıöçĞÜŞİÖÇ]{3,}", soru_stripped, re.UNICODE)
    if len(words) < _MIN_REAL_WORD_COUNT:
        return True

    # 5. Tek kelimeli sosyal ifadeler: "merhaba", "tamam", "teşekkür", "selam" vb.
    # Bu kelimeler tek başına hiçbir zaman klinik soru olamaz.
    # NOT: Birden fazla kelime içeriyorsa (ör: "tamam da ftr?") bu kontrolü atlıyoruz —
    # o durumda bağlam füzyonu LLM'e bırakılır.
    words_lower = {w.lower() for w in words}
    # Tek kelimeli girdi VE bu kelime sosyal listede → reddet
    if len(words) == 1 and words_lower.issubset(_SOCIAL_ONLY_WORDS):
        return True

    return False

# ─── LLM Sentinel Sabiti ──────────────────────────────────────────────────────
# LLM bu değeri döndürürse preprocessor klinik_degil=True flag'ini ayarlar.
# Blacklist'e değil, LLM'in anlama kapasitesine dayanan ölçeklenebilir yaklaşım.
_NON_CLINICAL_SENTINEL = "__KLINIK_DEGIL__"

# ─── LLM Reformülasyon Sistem Promptu ────────────────────────────────────────
_REWRITE_SYSTEM_PROMPT = """Sen bir tıbbi sorgu optimizasyon asistanısın. Görevin kısa veya konuşma dili
ile yazılmış klinik soruları, klinik kılavuz metinleriyle daha iyi eşleşmesi için
akademik Türkçe tıbbi terminolojiye çevirmek.

KURALLAR:
1. Sorunun klinik anlamını KORU, yorumlama veya genişletme.
2. Kısaltmaları tam ifadelerine çevir (FTR → Fiziksel Tıp ve Rehabilitasyon).
3. Sohbet dili ifadelerini ("tamam da", "yani", "peki") çıkar.
4. Önceki konu bağlamı verildiyse (BAĞLAM: satırı), soruyu o konuyla ilişkilendir.
5. SADECE yeniden yazılmış sorguyu döndür — başka hiçbir şey yazma.
6. Maksimum 2 cümle.
7. Türkçe yaz.

KRİTİK KURAL — KLİNİK OLMAYAN GİRDİ TESPİTİ:
Eğer SORGU aşağıdaki kategorilerden birine giriyorsa, YALNIZCA şu metni yaz:
__KLINIK_DEGIL__
(Hiçbir şey reformüle etme, hiçbir açıklama ekleme — sadece bu sentinel değeri.)

Klinik OLMAYAN kategoriler:
- Gülme/ses taklidi: "haha", "hehe", "hahahahaha", "ahahaha", "hı hı"
- Anlamsız klavye girdisi: "asdfgh", "qwerty", "12345"
- Selamlama/veda: "merhaba", "günaydın", "iyi günler", "görüşürüz"
- Teşekkür/onay/red: "teşekkür", "sağol", "tamam", "evet", "hayır", "bravo"
- Duygusal/sosyal ifade: "süper", "harika", "mükemmel", "dur", "bilmiyorum", "ne bileyim"
- Soru formatında olsa bile klinik içerik YOKSA: "nasılsın?", "ne zaman gelirsin?"
- Sadece noktalama veya emoji

Klinik OLAN kategoriler (bunları reformüle et):
- Hastalık, belirti, tanı sorguları: "pasi nedir", "deri döküntüsü"
- Tedavi, ilaç, doz sorguları: "metotreksat başlanır mı", "biyolojik ne zaman"
- Kılavuz referansları: "sevk kriterleri", "takip aralığı"
- Bağlam gerektiren devam soruları: "peki bu hastada ne yapmalı", "o zaman dozu?"
  (önceki konu tıbbi ise bu da tıbbi kabul edilir)"""


# ─── Veri Yapısı ─────────────────────────────────────────────────────────────

@dataclass
class ConversationTurn:
    """Tek bir sohbet turu: hekim sorusu + AI yanıtı."""
    soru: str
    cevap: str


@dataclass
class PreprocessResult:
    """Ön işleme sonucu."""
    zengin_sorgu: str          # ChromaDB'ye gidecek zenginleştirilmiş sorgu
    orijinal_sorgu: str        # QA engine'e gidecek değişmez orijinal sorgu
    onisleme_yapildi: bool     # Değişiklik yapıldı mı?
    llm_kullanildi: bool       # LLM çağrısı yapıldı mı?
    onisleme_suresi_ms: float  # Preprocessor işlem süresi
    klinik_degil: bool = False # True ise girdi klinik soru değil → pipeline durdurulmalı


# ─── Preprocessor ────────────────────────────────────────────────────────────

class QueryPreprocessor:
    """
    İki aşamalı sorgu ön işleyici.

    Kullanım:
        preprocessor = QueryPreprocessor(api_key="...", model_name="models/gemini-3.5-flash-lite")
        result = await preprocessor.preprocess(
            soru="tamam da ftr ye gidecek olan hastaya nelerin yapılacağını demem lazım",
            gecmis=[ConversationTurn(soru="PsA şüphesiyle FTR sevki...", cevap="...")]
        )
        # result.zengin_sorgu → ChromaDB araması için
        # result.orijinal_sorgu → QA engine için
    """

    def __init__(self, api_key: str, model_name: str = PREPROCESSOR_MODEL) -> None:
        genai.configure(api_key=api_key)
        self._model_name = model_name
        self._model: Optional[genai.GenerativeModel] = None
        self._llm_available = False
        self._init_llm()

    def _init_llm(self) -> None:
        """LLM başlatmayı dene. Başarısız olursa kural tabanlı modda çalış."""
        try:
            self._model = genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=_REWRITE_SYSTEM_PROMPT,
                generation_config=genai.GenerationConfig(
                    temperature=0.0,          # Deterministik reformülasyon
                    max_output_tokens=PREPROCESSOR_MAX_TOKENS,
                ),
            )
            self._llm_available = True
            logger.info("[Preprocessor] %s hazır (LLM modu).", self._model_name)
        except Exception as exc:
            logger.warning(
                "[Preprocessor] LLM başlatılamadı (%s). Kural tabanlı modda çalışılacak.",
                exc,
            )
            self._llm_available = False

    async def preprocess(
        self,
        soru: str,
        gecmis: list[ConversationTurn] | None = None,
    ) -> PreprocessResult:
        """
        Sorguyu zenginleştir.

        Args:
            soru: Hekimin ham sorusu.
            gecmis: Son 3 Q/A çifti (opsiyonel). Sohbet bağlamı için.

        Returns:
            PreprocessResult — zengin sorgu + meta bilgiler.
            NOT: klinik_degil=True ise caller pipeline'ı durdurmalı.
        """
        import time
        t0 = time.perf_counter()

        gecmis = gecmis or []

        # Adım 0: Klinik dışı girdi erken tespiti (0ms, her zaman çalışır)
        # Bu adım LLM'den önce gelir — anlamsız girdi LLM'e hiç ulaşmaz.
        if _is_non_clinical_input(soru):
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "[Preprocessor] Klinik dışı girdi tespit edildi, pipeline durduruldu: %r",
                soru,
            )
            return PreprocessResult(
                zengin_sorgu=soru,
                orijinal_sorgu=soru,
                onisleme_yapildi=False,
                llm_kullanildi=False,
                onisleme_suresi_ms=round(elapsed_ms, 1),
                klinik_degil=True,
            )

        # Adım 1: Kural tabanlı kısaltma genişletme (0ms, her zaman çalışır)
        kisaltma_genisletilmis = self._expand_abbreviations(soru)
        abbreviations_changed = kisaltma_genisletilmis != soru

        # Adım 2: LLM gerekli mi? Tetiklenme koşullarını kontrol et
        llm_gerekli = self._should_rewrite_with_llm(
            orijinal=soru,
            genisletilmis=kisaltma_genisletilmis,
            gecmis=gecmis,
        )

        zengin_sorgu = kisaltma_genisletilmis
        llm_kullanildi = False

        if llm_gerekli and self._llm_available:
            try:
                onceki_konu = self._extract_previous_topic(gecmis)
                llm_sonucu = await self._rewrite_with_llm(
                    soru=kisaltma_genisletilmis,
                    onceki_konu=onceki_konu,
                )
                # ── Sentinel kontrolü: LLM klinik olmadığını işaret etti mi? ──
                if llm_sonucu and _NON_CLINICAL_SENTINEL in llm_sonucu:
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    logger.info(
                        "[Preprocessor] LLM sentinel tespiti → klinik dışı girdi: %r",
                        soru,
                    )
                    return PreprocessResult(
                        zengin_sorgu=soru,
                        orijinal_sorgu=soru,
                        onisleme_yapildi=False,
                        llm_kullanildi=False,
                        onisleme_suresi_ms=round(elapsed_ms, 1),
                        klinik_degil=True,
                    )
                # ── Normal reformülasyon ──────────────────────────────────────
                if llm_sonucu and len(llm_sonucu) >= 10:
                    zengin_sorgu = llm_sonucu
                    llm_kullanildi = True
                    logger.info(
                        "[Preprocessor] LLM reformülasyonu:\n  Orijinal: %s\n  Zengin:   %s",
                        soru, zengin_sorgu,
                    )
            except Exception as exc:
                # Graceful degradation: LLM başarısız olursa kısaltma genişletilmiş sorgu kullan
                logger.warning("[Preprocessor] LLM reformülasyonu başarısız: %s. Kısaltma genişletme kullanılıyor.", exc)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return PreprocessResult(
            zengin_sorgu=zengin_sorgu,
            orijinal_sorgu=soru,
            onisleme_yapildi=abbreviations_changed or llm_kullanildi,
            llm_kullanildi=llm_kullanildi,
            onisleme_suresi_ms=round(elapsed_ms, 1),
            klinik_degil=False,
        )

    # ─── Yardımcı Metodlar ────────────────────────────────────────────────────

    @staticmethod
    def _expand_abbreviations(text: str) -> str:
        """
        Kural tabanlı kısaltma genişletme — tek geçişli algoritma.

        Neden tek geçiş?
            Çok geçişli replace, kısaltmanın genişletilmiş halindeki kelimeleri
            tekrar eşleştirebilir (ör: "biyosi" → "biyolojik ajan" → "biyolojik"
            kısaltması tekrar eşleşir → çifte genişletme).
            Tek geçiş bu sorunu köklü çözer.

        Algoritma:
            1. Metni token'lara böl (kelime ve kelime-dışı parçalar)
            2. Her token için kısaltma sözlüğünde eşleşme ara
            3. Eşleşme varsa genişletilmiş halle değiştir, yoksa olduğu gibi bırak
            4. Token'ları birleştir
        """
        # Türkçe kesme işaretli ekleri de kapsayan token regex
        # Örn: "ftr'ye", "psa'da" bütün olarak yakalanır
        token_pattern = re.compile(r"[\w]+(?:'[\w]+)?", re.UNICODE)

        def replace_token(match: re.Match) -> str:
            token = match.group(0)
            token_lower = token.lower()
            # Tam eşleşme ara (büyük/küçük harf duyarsız)
            if token_lower in MEDICAL_ABBREVIATIONS:
                return MEDICAL_ABBREVIATIONS[token_lower]
            return token

        return token_pattern.sub(replace_token, text)

    @staticmethod
    def _should_rewrite_with_llm(
        orijinal: str,
        genisletilmis: str,
        gecmis: list[ConversationTurn],
    ) -> bool:
        """
        LLM reformülasyonuna ihtiyaç var mı?

        Koşul A: Kısa sorgu (≤8 kelime) VE tıbbi terim YOK
        Koşul B: Devam sorusu göstergesi VAR VE geçmiş mevcut
        """
        kelimeler = genisletilmis.split()
        kelime_sayisi = len(kelimeler)

        # Koşul A: Kısa sorgu ve tıbbi terim yok
        if kelime_sayisi <= 8 and not _MEDICAL_TERM_PATTERN.search(genisletilmis):
            logger.debug("[Preprocessor] Koşul A tetiklendi (kısa/terminolojisiz sorgu, %d kelime).", kelime_sayisi)
            return True

        # Koşul B: Devam sorusu göstergesi VE geçmiş var
        if gecmis:
            sorgu_kucuk = genisletilmis.lower()
            for keyword in CONTINUATION_KEYWORDS:
                if keyword in sorgu_kucuk:
                    logger.debug("[Preprocessor] Koşul B tetiklendi (devam sorusu: '%s').", keyword)
                    return True

        return False

    @staticmethod
    def _extract_previous_topic(gecmis: list[ConversationTurn]) -> str:
        """
        Sohbet geçmişinden önceki konuyu özetle.
        Sadece son Q/A çiftinin sorusunu kullan — basit ve yeterli.
        """
        if not gecmis:
            return ""
        son_tur = gecmis[-1]
        # Sorunun ilk 200 karakteri yeterli bağlamı sağlar
        return son_tur.soru[:200]

    async def _rewrite_with_llm(
        self,
        soru: str,
        onceki_konu: str,
    ) -> str:
        """
        gemini-3.5-flash-lite ile sorguyu tıbbi terminolojiye yeniden yaz.
        Async çağrı — FastAPI event loop'unu bloklamaz.
        """
        if not self._model:
            raise RuntimeError("LLM modeli başlatılmamış.")

        prompt_parts = []
        if onceki_konu:
            prompt_parts.append(f"BAĞLAM (önceki konu): {onceki_konu}")
        prompt_parts.append(f"SORGU: {soru}")
        prompt = "\n".join(prompt_parts)

        # generate_content_async → FastAPI coroutine'i bloklamaz (sert zaman aşımı ile)
        response = await self._model.generate_content_async(
            prompt,
            request_options={"timeout": PREPROCESSOR_TIMEOUT_SEC},
        )
        return response.text.strip()
