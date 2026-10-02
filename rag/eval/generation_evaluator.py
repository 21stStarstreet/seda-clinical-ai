"""
RAG Generation (Üretim) Değerlendiricisi.
Atıf doğruluğu, alıntı sadakati (verbatim quote), kilit nokta ve sayısal doğruluk testleri.
"""

from __future__ import annotations

import re
import time
import logging
from typing import List, Tuple, Optional

from rag.eval.schema import (
    GoldenQuestion,
    GenerationResultItem,
    GenerationSummary,
    CitationVerificationItem,
    QuoteVerificationItem,
)
from rag.retriever import Retriever, RetrievalResponse
from rag.qa_engine import QAEngine, QAResponse

logger = logging.getLogger(__name__)


TR_ASCII_MAP = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigguussöocc")

def _normalize_text(text: str) -> str:
    """Metni karşılaştırma için küçük harfe ve tekil boşluklara indirger."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


CLINICAL_SYNONYMS: dict[str, list[str]] = {
    "pasi": ["pasi", "paşi", "pasi 75", "pasi 90", "pasi skor", "pasi'de"],
    "paşi": ["pasi", "paşi"],
    "bsa": ["bsa", "vya", "vücut yüzey", "vucut yuzey"],
    "vya": ["bsa", "vya", "vücut yüzey"],
    "dlqi": ["dlqi", "dyki", "yaşam kalite", "yasam kalite"],
    "dyki": ["dlqi", "dyki", "yaşam kalite"],
    "dgd": ["dgd", "pga"],
    "ppd": ["ppd", "tdt", "tüberkülin", "tuberculin", "tüberkülin deri"],
    "tdt": ["ppd", "tdt", "tüberkülin"],
    "igra": ["igra", "igst", "interferon", "quantiferon"],
    "igst": ["igra", "igst", "interferon"],
    "izoniazid": ["izoniazid", "isoniazid", "inh"],
    "inh": ["inh", "izoniazid", "isoniazid"],
    "mtx": ["mtx", "metotreksat", "methotrexate"],
    "csa": ["csa", "siklosporin", "cyclosporin", "ciclosporin"],
    "alt": ["alt", "alanin", "transaminaz", "karaciğer", "kcft", "hepatik"],
    "ast": ["ast", "aspartat", "transaminaz", "karaciğer", "kcft", "hepatik"],
    "hemogram": ["hemogram", "tam kan", "fbc", "cbc", "lökosit", "trombosit"],
    "karaciğer fonksiyon testleri": ["kcft", "alt", "ast", "karaciğer", "hepatik"],
    "kreatinin": ["kreatinin", "serum kreatinin", "böbrek", "renal"],
    "hepatit": ["hepatit", "hbv", "hcv", "hbsag"],
    "gebelik testi": ["gebelik", "beta-hcg", "hcg"],
    "folik asit": ["folik asit", "folat", "folbiol"],
    "haftalık tek doz": ["haftalık", "haftada bir", "haftada 1"],
    "doz azaltımı": ["doz azalt", "dozun azalt", "doz düş", "doz ind", "kesil"],
    "kan basıncı takibi": ["kan basınc", "tansiyon", "hipertansiyon"],
    "nefrotoksisite": ["nefrotoks", "renal toks", "böbrek toks", "kreatinin", "renal"],
    "azalma": ["azalma", "iyileşme", "gerileme", "düzelme"],
    "iyileşme": ["azalma", "iyileşme", "gerileme", "düzelme"],
    "orta-şiddetli psoriazis": ["orta-şiddetli", "orta şiddetli", "sistemik tedavi"],
    "kseroderma pigmentosum": ["kseroderma", "xeroderma", "xp"],
    "lupus eritematozus": ["lupus", "sle", "le"],
    "fotosensitivite": ["fotosensitivite", "ışık duyarlılığı", "güneş"],
    "entezit": ["entezit", "enthesitis", "eklem"],
    "daktilit": ["daktilit", "dactylitis", "sosis parmak"],
    "sabah tutukluğu": ["sabah tutukluğu", "sabah sertliği", "morning stiffness"],
    "caspar": ["caspar", "psoriatik artrit", "artrit kriter"],
    "candida": ["candida", "kandida", "kandidiyazis", "mantar", "mukokutanöz"],
    "biosimilar": ["biosimilar", "biyobenzer", "biyobenzerler", "switching"],
    "fibroscan": ["fibroscan", "elastografi", "karaciğer biyopsisi", "karaciğer elastografisi"],
    "tenofovir": ["tenofovir", "antiviral", "profilaksi", "entekavir"],
    "steatohepatit": ["steatohepatit", "karaciğer yağlanması", "nash", "mash", "hepatik steatoz"],
    "özel lokalizasyonlar": ["özel lokalizasyon", "tırnak", "saçlı deri", "palmoplantar", "genital"],
    "eklem ve deri yanıtı": ["eklem ve deri", "eklem ve cilt", "her iki tutulum", "cilt ve eklem", "eklem ve deri yanıtı"],
    "dar bant UVB daha güvenli": ["dar bant", "nb-uvb", "nbuvb", "daha güvenli", "daha az karsinojenik"],
    "gastroenteroloji danışımı": ["gastroenteroloji", "gastroenterolog", "danışım", "konsültasyon"],
    "immünsüpresyondan kaçınma": ["immünsüpresyondan kaçınma", "immünsüpresyon", "bağışıklık baskılanması"],
    "indüksiyon sonu": ["indüksiyon", "primer değerlendirme", "hafta"],
    "Fc parçası eksik": ["fc parçası", "fc bölgesi", "pegol", "plasental geçiş"],
    "BCG aşılı": ["bcg", "aşı", "aşılanmış", "ppd"],
    "kontrendike": ["kontrendike", "kesinlikle kontrendike", "kaçınılmalı", "kontrendikedir"],
}

ROMAN_TO_ARABIC = {
    "VI": "6",
    "IV": "4",
    "V": "5",
    "III": "3",
    "II": "2",
    "I": "1",
}

WORD_TO_DIGIT = {
    "kırkbeş": "45",
    "kırk beş": "45",
    "on beş": "15",
    "onbes": "15",
    "elli": "50",
    "kırk": "40",
    "otuz": "30",
    "yirmi": "20",
    "on": "10",
    "beş": "5",
    "dört": "4",
    "üç": "3",
    "iki": "2",
    "bir": "1",
}


REBUTTAL_KEYWORDS: list[str] = [
    "önerilmez",
    "onerilmez",
    "kontrendike",
    "kontrendikedir",
    "ilk basamak değil",
    "ilk basamak degil",
    "birinci basamak değil",
    "birinci basamak degil",
    "kılavuzda yer almıyor",
    "kilavuzda yer almiyor",
    "kılavuzda yer almaz",
    "kilavuzda yer almaz",
    "yer almamaktadır",
    "önerilmemektedir",
    "onerilmemektedir",
    "kaçınılmalıdır",
    "kacinilmalidir",
    "not recommended",
    "contraindicated",
    "is not a first-line",
    "is not recommended",
]


def _normalize_numbers_in_text(text: str) -> str:
    """Sayısal karşılaştırma için Roma rakamlarını, Türkçe yazı sayılarını ve ondalıkları normalize eder."""
    if not text:
        return ""
    # 1. Noktalı virgül / virgül ondalık ayracı: "0,5" -> "0.5"
    t = re.sub(r"(\d+),(\d+)", r"\1.\2", text)
    # 2. Sayı yazıyla -> rakama (büyükten küçüğe sıralı)
    for w, d in WORD_TO_DIGIT.items():
        t = re.sub(r"\b" + re.escape(w) + r"\b", d, t, flags=re.IGNORECASE)
    # 3. Roma rakamı -> Arap rakamı (yalnızca word boundary ile)
    for r, d in ROMAN_TO_ARABIC.items():
        t = re.sub(r"\b" + re.escape(r) + r"\b", d, t, flags=re.IGNORECASE)
    return t


def _is_keypoint_covered(kp: str, answer_text: str) -> bool:
    """Klinik kilit noktanın cevapta eşanlamlılar veya kısaltmalar dahil varlığını sınar."""
    ans_norm = _normalize_text(answer_text)
    ans_ascii = ans_norm.translate(TR_ASCII_MAP)
    kp_norm = _normalize_text(kp)
    kp_ascii = kp_norm.translate(TR_ASCII_MAP)

    if kp_norm in ans_norm or kp_ascii in ans_ascii:
        return True

    # Parçalara ve klinik eşanlamlılara bak
    tokens = [t for t in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9%><]+", kp_norm) if len(t) >= 3 or t.isdigit()]
    for t in tokens:
        t_clean = t.strip("><%")
        if t in CLINICAL_SYNONYMS:
            if any(syn in ans_norm or syn.translate(TR_ASCII_MAP) in ans_ascii for syn in CLINICAL_SYNONYMS[t]):
                return True
        if t_clean in CLINICAL_SYNONYMS:
            if any(syn in ans_norm or syn.translate(TR_ASCII_MAP) in ans_ascii for syn in CLINICAL_SYNONYMS[t_clean]):
                return True
        if len(t) >= 3 and (t in ans_norm or t.translate(TR_ASCII_MAP) in ans_ascii):
            return True

    return False


def _is_number_covered(num: str, answer_text: str) -> bool:
    """Sayısal değerin normalize edilmiş formda cevapta yer alıp almadığını kontrol eder."""
    norm_ans = _normalize_numbers_in_text(answer_text.lower())
    clean_num = num.replace("%", "").strip()
    norm_target = _normalize_numbers_in_text(clean_num.lower())

    # Tire ile yazılmış sayılar: "III-IV" veya "10-15" -> her iki parçayı da ara
    if "-" in norm_target:
        parts = [p.strip() for p in norm_target.split("-") if p.strip()]
        if parts:
            return all(bool(re.search(r"\b" + re.escape(p) + r"\b", norm_ans)) for p in parts)

    # Tekil sayı kontrolü
    return bool(re.search(r"\b" + re.escape(norm_target) + r"\b", norm_ans))


class GenerationEvaluator:
    """
    LLM yanıtlarının klinik doğruluğunu ve atıf sadakatini ölçen modül.
    """

    def __init__(self, qa_engine: QAEngine, retriever: Retriever) -> None:
        self._qa = qa_engine
        self._retriever = retriever

    def evaluate_question(self, question: GoldenQuestion) -> GenerationResultItem:
        """
        Tek bir soru için uçtan uca üretim kalitesini test eder.
        """
        t0 = time.perf_counter()
        retrieval_res: RetrievalResponse = self._retriever.retrieve(question.soru)
        qa_res: QAResponse = self._qa.answer(question.soru, retrieval_res)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        errors: List[str] = []

        # Fallback / Timeout kontrolü
        is_fallback = False
        fallback_reason = None
        ans_text = qa_res.cevap or ""

        if getattr(qa_res, "fallback_kullanildi", False):
            is_fallback = True
            fallback_reason = "fallback_kullanildi=True (Gemini hata/timeout/güvenlik)"
        elif ans_text.startswith("Kılavuz sorgusu şu an yanıt üretemedi") or ans_text.startswith("LLM yanıt üretemedi"):
            is_fallback = True
            fallback_reason = "Fallback yanıt prefix'i tespit edildi"

        # 1. Çekimserlik / Yanlış Öncül Başarımı
        oncul_durum = None
        if is_fallback:
            dogru_cekimserlik = False
            errors.append(f"Fallback/Timeout: {fallback_reason}")
        elif question.tur == "yanlis_oncul":
            ans_lower = ans_text.lower()
            if qa_res.bulunamadi:
                dogru_cekimserlik = True
                oncul_durum = "reddetti"
            elif any(k in ans_lower for k in REBUTTAL_KEYWORDS):
                dogru_cekimserlik = True
                oncul_durum = "curuttu"
            else:
                dogru_cekimserlik = False
                oncul_durum = "hata"
                errors.append("Yanlış öncül kabul edildi veya çürütülmedi (halüsinasyon/yanlış bilgi riski).")
        elif not question.kapsam_ici:
            dogru_cekimserlik = qa_res.bulunamadi
            if not qa_res.bulunamadi:
                errors.append("Kapsam dışı soruda bulunamadi: True dönmedi (halüsinasyon riski).")
        else:
            dogru_cekimserlik = (not qa_res.bulunamadi)
            if qa_res.bulunamadi:
                errors.append("Kapsam içi soruda çekimser kalındı (bulunamadi: True).")

        # 2. Atıf Doğruluğu (Citation Precision)
        citations: List[CitationVerificationItem] = []
        valid_citations = 0

        for src in qa_res.kaynaklar:
            matched_in_context = any(
                (h.source_code == src.kaynak_kodu and abs(h.doc_page - src.sayfa) <= 1)
                for h in retrieval_res.hits
            )
            citations.append(
                CitationVerificationItem(
                    kaynak_kodu=src.kaynak_kodu,
                    sayfa=src.sayfa,
                    in_retrieved_context=matched_in_context,
                )
            )
            if matched_in_context:
                valid_citations += 1
            else:
                errors.append(f"Uydurma atıf: {src.kaynak_kodu} s.{src.sayfa} bağlamda mevcut değil!")

        citation_precision = (valid_citations / len(citations)) if citations else 1.0

        # 3. Alıntı Sadakati (Verbatim Quote Veracity)
        quotes: List[QuoteVerificationItem] = []
        valid_quotes = 0

        for src in qa_res.kaynaklar:
            quote_text = src.alinti or ""
            norm_quote = _normalize_text(quote_text)

            is_exact = False
            is_fuzzy = False

            if norm_quote:
                for hit in retrieval_res.hits:
                    if hit.source_code == src.kaynak_kodu and abs(hit.doc_page - src.sayfa) <= 1:
                        norm_chunk = _normalize_text(hit.text)
                        if norm_quote in norm_chunk:
                            is_exact = True
                            is_fuzzy = True
                            break
                        words = norm_quote.split()
                        if len(words) >= 4:
                            sub_phrase = " ".join(words[:4])
                            if sub_phrase in norm_chunk:
                                is_fuzzy = True

            quotes.append(
                QuoteVerificationItem(
                    alinti=quote_text,
                    kaynak_kodu=src.kaynak_kodu,
                    sayfa=src.sayfa,
                    is_exact_match=is_exact,
                    is_fuzzy_match=is_fuzzy,
                )
            )
            if is_exact or is_fuzzy:
                valid_quotes += 1
            elif quote_text:
                errors.append(f"Doğrulanamayan alıntı: '{quote_text[:50]}...'")

        quote_veracity = (valid_quotes / len(quotes)) if quotes else 1.0

        # 4. Kilit Nokta Kapsaması (Keypoint Coverage)
        covered_keypoints = 0
        missing_keypoints = []

        if not is_fallback and question.kapsam_ici and question.kilit_noktalar:
            for kp in question.kilit_noktalar:
                if _is_keypoint_covered(kp, ans_text):
                    covered_keypoints += 1
                else:
                    missing_keypoints.append(kp)
            keypoint_coverage = covered_keypoints / len(question.kilit_noktalar)
        elif is_fallback:
            keypoint_coverage = 0.0
        else:
            keypoint_coverage = 1.0

        # 5. Sayısal Eşik Doğruluğu
        covered_numbers = 0
        missing_numbers = []

        if not is_fallback and question.kapsam_ici and question.sayisal_degerler:
            for num in question.sayisal_degerler:
                if _is_number_covered(num, ans_text):
                    covered_numbers += 1
                else:
                    missing_numbers.append(num)
            numerical_accuracy = covered_numbers / len(question.sayisal_degerler)
        elif is_fallback:
            numerical_accuracy = 0.0
        else:
            numerical_accuracy = 1.0

        return GenerationResultItem(
            question_id=question.id,
            soru=question.soru,
            tur=question.tur,
            kapsam_ici=question.kapsam_ici,
            bulunamadi=qa_res.bulunamadi,
            dogru_cekimserlik=dogru_cekimserlik,
            cevap_metni=qa_res.cevap,
            citations=citations,
            citation_precision=round(citation_precision, 4),
            quotes=quotes,
            quote_veracity=round(quote_veracity, 4),
            kilit_nokta_kapsama=round(keypoint_coverage, 4),
            sayisal_dogruluk=round(numerical_accuracy, 4),
            eksik_kilit_noktalar=missing_keypoints,
            eksik_sayisal_degerler=missing_numbers,
            islem_suresi_ms=round(latency_ms, 1),
            is_fallback=is_fallback,
            fallback_reason=fallback_reason,
            oncul_durum=oncul_durum,
            hatalar=errors,
        )

    def run(self, questions: List[GoldenQuestion]) -> Tuple[List[GenerationResultItem], GenerationSummary]:
        """
        Altın set üzerinde üretim değerlendirmesini çalıştırır.
        """
        results: List[GenerationResultItem] = []
        for idx, q in enumerate(questions, start=1):
            logger.info("[GenEval] Soru %d/%d işleniyor: %s", idx, len(questions), q.id)
            res = self.evaluate_question(q)
            results.append(res)
            # API rate limit koruması için kısa nefes
            time.sleep(1.0)

        # Fallback soruları ayıkla
        fallback_items = [r for r in results if r.is_fallback]
        fallback_questions_list = [
            {
                "id": r.question_id,
                "soru": r.soru,
                "neden": r.fallback_reason or "LLM timeout / boş yanıt",
            }
            for r in fallback_items
        ]

        valid_results = [r for r in results if not r.is_fallback]

        # Kapsam dışı çekimserlik
        out_of_scope = [r for r in valid_results if not r.kapsam_ici]
        proper_refusals = sum(1 for r in out_of_scope if r.dogru_cekimserlik)
        proper_refusal_rate = (proper_refusals / len(out_of_scope)) if out_of_scope else 1.0

        # Kapsam içi geçerli sorular (fallback'ler paydadan çıkarıldı)
        in_scope_valid = [r for r in valid_results if r.kapsam_ici]
        mean_citation = sum(r.citation_precision for r in in_scope_valid) / len(in_scope_valid) if in_scope_valid else 1.0
        mean_quote = sum(r.quote_veracity for r in in_scope_valid) / len(in_scope_valid) if in_scope_valid else 1.0
        mean_kp = sum(r.kilit_nokta_kapsama for r in in_scope_valid) / len(in_scope_valid) if in_scope_valid else 1.0
        mean_num = sum(r.sayisal_dogruluk for r in in_scope_valid) / len(in_scope_valid) if in_scope_valid else 1.0
        avg_latency = sum(r.islem_suresi_ms for r in results) / len(results) if results else 0.0

        # Yanlış öncül istatistikleri
        yanlis_oncul_items = [r for r in results if r.tur == "yanlis_oncul"]
        curuttu_count = sum(1 for r in yanlis_oncul_items if r.oncul_durum == "curuttu")
        reddetti_count = sum(1 for r in yanlis_oncul_items if r.oncul_durum == "reddetti")
        hata_count = sum(1 for r in yanlis_oncul_items if r.oncul_durum == "hata")
        total_yo = len(yanlis_oncul_items)
        success_yo = curuttu_count + reddetti_count
        yanlis_oncul_stats = {
            "toplam": total_yo,
            "basarili": success_yo,
            "curuttu": curuttu_count,
            "reddetti": reddetti_count,
            "hata": hata_count,
        }

        summary = GenerationSummary(
            total_evaluated=len(results),
            proper_refusal_rate=round(proper_refusal_rate, 4),
            mean_citation_precision=round(mean_citation, 4),
            mean_quote_veracity=round(mean_quote, 4),
            mean_keypoint_coverage=round(mean_kp, 4),
            mean_numerical_accuracy=round(mean_num, 4),
            avg_latency_ms=round(avg_latency, 1),
            fallback_count=len(fallback_items),
            fallback_questions=fallback_questions_list,
            yanlis_oncul_stats=yanlis_oncul_stats,
        )

        return results, summary
