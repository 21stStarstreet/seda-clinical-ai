"""
Çift Dilli (TR ↔ EN) Dermatoloji Terim Genişletme Sözlüğü.
Türkçe klinik sorguları İngilizce EuroGuiDerm kavramlarıyla zenginleştirir.
"""

from __future__ import annotations

import re
from typing import List, Dict

# ─── Çift Dilli Klinik Terim Eşleme Tablosu ────────────────────────────────────

CLINICAL_BILINGUAL_MAP: Dict[str, List[str]] = {
    # İlaçlar ve Kısaltmalar
    "metotreksat": ["methotrexate", "mtx"],
    "mtx": ["methotrexate", "metotreksat"],
    "siklosporin": ["cyclosporine", "ciclosporin", "csa"],
    "asitretin": ["acitretin", "retinoid"],
    "adalimumab": ["adalimumab", "anti-tnf", "humira"],
    "infliksimab": ["infliximab", "remicade"],
    "etanersept": ["etanercept", "enbrel"],
    "sertolizumab": ["certolizumab", "cimzia"],
    "certolizumab": ["certolizumab pegol", "cimzia"],
    "ustekinumab": ["ustekinumab", "stelara", "anti-il-12/23"],
    "sekukinumab": ["secukinumab", "cosentyx", "anti-il-17"],
    "cosentyx": ["secukinumab", "300 mg"],
    "iksekizumab": ["ixekizumab", "taltz", "anti-il-17"],
    "taltz": ["ixekizumab", "160 mg"],
    "bimekizumab": ["bimekizumab", "bimzelx"],
    "guselkumab": ["guselkumab", "tremfya", "anti-il-23"],
    "risankizumab": ["risankizumab", "skyrizi"],
    "tildrakizumab": ["tildrakizumab", "ilumya"],
    "apremilast": ["apremilast", "otezla", "pde4"],
    "deukravasitinib": ["deucravacitinib", "sotyktu", "tyk2"],

    # Klinik Durumlar ve Özel Popülasyonlar
    "gebelik": ["pregnancy", "pregnant", "lactation", "teratogenic", "placental transfer"],
    "emzirme": ["breastfeeding", "lactation"],
    "doğurganlık": ["fertility", "conception"],
    "biyobenzer": ["biosimilar", "biosimilars", "switching", "interchangeability"],
    "tırnak": ["nail psoriasis", "napsi", "nail involvement"],
    "yüksük tırnak": ["nail pitting", "pitting"],
    "eklem": ["joint", "psoriatic arthritis", "psa", "caspar"],
    "psoriatik artrit": ["psoriatic arthritis", "psa", "arthritis"],
    "sabah tutukluğu": ["morning stiffness", "stiffness > 30 min"],
    "daktilit": ["dactylitis", "sausage digit"],
    "entezit": ["enthesitis"],
    "kandidiyazis": ["candida", "candidiasis", "fungal infection"],
    "kandida": ["candida", "mucocutaneous infection"],
    "tüberküloz": ["tuberculosis", "tb", "latent tb", "ppd", "igra", "quantiferon"],
    "verem": ["tuberculosis", "tb"],
    "hepatit": ["hepatitis", "hbv", "hcv", "hbsag"],
    "karaciğer": ["liver enzymes", "hepatic", "alt", "ast", "fibroscan"],
    "böbrek": ["renal", "kidney", "creatinine"],
    "kalp yetmezliği": ["heart failure", "nyha", "cardiac"],
    "kanser": ["malignancy", "cancer", "solid tumor", "lymphoma"],
    "malignite": ["malignancy", "cancer"],
    "fototerapi": ["phototherapy", "nb-uvb", "nbuvb", "puva"],
    "puva": ["puva", "psoralen"],
    "püstüler": ["pustular", "generalized pustular psoriasis", "gpp"],
    "eritrodermik": ["erythrodermic", "erythroderma"],
    "paradoksal": ["paradoxical psoriasis", "paradoxical flare"],
    "aşı": ["vaccine", "vaccination", "live vaccine", "live attenuated"],
    "canlı aşı": ["live attenuated vaccine", "live vaccine contraindicated"],
    "yanıt": ["treatment goal", "pasi 75", "pasi 90", "pasi 100", "efficacy"],
    "hedef": ["treatment goal", "response", "mcid"],
    "indüksiyon": ["induction phase", "induction dose", "loading dose"],
    "idame": ["maintenance phase", "maintenance dose"],
    "kesilme": ["discontinuation", "cessation", "withdrawal"],
    "obezite": ["obesity", "bmi", "metabolic syndrome", "overweight"],
    "vki": ["bmi", "body mass index"],

    # Branşlar, Sevk ve Konsültasyon
    "fizik tedavi": ["physical therapy", "rehabilitation", "psoriatic arthritis", "kas iskelet sistemi", "eklem tutulumu"],
    "fiziksel tıp": ["physical therapy and rehabilitation", "psoriatic arthritis", "rehabilitation", "kas iskelet"],
    "romatoloji": ["rheumatology", "rheumatologist", "psoriatic arthritis", "joint involvement"],
    "konsültasyon": ["consultation", "referral", "interdisciplinary", "sevk"],
    "yönlendirme": ["referral", "consultation", "sevk"],
    "sevk": ["referral", "consultation", "yönlendirme"],

    # Eşanlamlı ve Çapraz Terimler
    "candida": ["kandidiyazis", "candida", "mucocutaneous infection"],
    "biosimilar": ["biyobenzer", "biosimilar", "biosimilars"],
    "inhibitör": ["antagonist", "inhibitor", "inhibitörleri"],
    "antagonist": ["inhibitör", "antagonist", "inhibitörleri"],
}


def expand_query_bilingual(query: str) -> str:
    """
    Türkçe sorgu metnindeki tıbbi terimleri tespit eder ve İngilizce
    kılavuzda karşılık bulan eşanlamlılarını sorgunun sonuna ekler.

    Örnek:
        Girdi:  "Sekukinumab gebelikte güvenli midir?"
        Çıktı: "Sekukinumab gebelikte güvenli midir? secukinumab cosentyx anti-il-17 pregnancy pregnant lactation"
    """
    lower_query = query.lower()
    additional_terms: List[str] = []

    # Çoklu kelimeli terimler önce aranır (örn: "sabah tutukluğu", "psoriatik artrit")
    for key, synonyms in CLINICAL_BILINGUAL_MAP.items():
        if " " in key and key in lower_query:
            additional_terms.extend(synonyms)

    # Tekil kelimeler
    words = re.findall(r"\b\w+\b", lower_query)
    for word in words:
        if word in CLINICAL_BILINGUAL_MAP and " " not in word:
            additional_terms.extend(CLINICAL_BILINGUAL_MAP[word])

    if not additional_terms:
        return query

    # Tekrarları ayıkla ve sorguya iliştir
    unique_terms = []
    seen = set(words)
    for t in additional_terms:
        t_clean = t.lower()
        if t_clean not in seen:
            seen.add(t_clean)
            unique_terms.append(t)

    if unique_terms:
        return f"{query} {' '.join(unique_terms[:8])}"
    return query
