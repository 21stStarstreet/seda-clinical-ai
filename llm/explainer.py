"""
LLM Açıklama Servisi
====================
Gemini API kullanarak ML kararını doktor dostu Türkçe'ye çevirir.

KRİTİK: LLM karar VERMİYOR — sadece ML kararını AÇIKLIYOR.
Tüm klinik kararlar XGBoost modeli tarafından üretilir.
LLM sadece bu kararı insan diline çevirir.

Kullanım:
    explainer = LLMExplainer(api_key=settings.gemini_api_key)
    detayli, ozet, is_fallback = explainer.explain(prediction_result, shap_explanation)
"""

from __future__ import annotations

from config.settings import settings, LABEL_NAMES, LABEL_DISPLAY_NAMES
from models.predictor import PredictionResult

# ─── Prompt Şablonları ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sen deneyimli bir dermatoloji uzmanının kıdemli asistanısın. Hekime yardımcı olmak üzere, hastanın klinik bulgularını ve belirlenen sevk kararlarını hem derinlemesine hem de özet olarak yazıya dökmek senin görevin.

GÖREV:
Sana verilen klinik bulguları ve sevk kararlarını iki ayrı metin olarak üreteceksin:
1. "detayli_epikriz": Bir üniversite hastanesi dermatoloji polikliniğinde kaleme alınmış kapsamlı bir konsültasyon notu. Her sevk kararı için ayrı paragraf, patofizyolojik gerekçe ve klinik bağlantı içeren, akıcı bir metin.
2. "kisa_ozet": Aynı kararları hekimin 10 saniyede kavrayabileceği, yalnızca aksiyona yönelik, son derece kısa ve net 2-3 cümlelik bir metin.

ZORUNLU ÇIKTI FORMATI - KESİNLİKLE SADE JSON FORMATINDA CEVAP VER:
{"detayli_epikriz": "...", "kisa_ozet": "..."}
JSON dışında hiçbir şey yazma. Açıklama, giriş cümlesi veya kod bloğu ekleme.

DİL VE TON KURALLARI (HER İKİ METİN İÇİN):
1. "Model", "Sistem", "Algoritma", "Güven skoru", "Parametre", "Negatif/Pozitif faktör" gibi yazılımsal kelimeleri ASLA KULLANMA.
2. İstatistiksel yüzde oranlarını (%87 gibi) metne kesinlikle yazma; "kuvvetle endikedir", "uygun görülmektedir", "klinik açıdan belirleyici niteliktedir" gibi doğal tıbbi ifadeler kullan.
3. Spesifik ilaç ismi önerme. Madde imi, tire veya bullet point KULLANMA — her şey paragraf halinde akmalıdır.
4. Her paragraf başına o sevk/kararın başlığını kalın (**Başlık:**) olarak yaz.

DETAYLI EPİKRİZ için: Her sevk kararı için ayrı, en az 4-5 cümleden oluşan bir paragraf. Patofizyolojik mantık, klinik risk ve hastanın bireysel bulguları arasındaki ilişkiyi kur.
KISA ÖZET için: "Özetle: ..." diye başlayan, tüm kararları birleştiren maksimum 2-3 cümle.
"""


def build_explanation_prompt(
    prediction: PredictionResult,
    shap_explanation: dict,
) -> str:
    """
    LLM için hasta-özel prompt oluştur.

    Args:
        prediction: ML modelinin tahmin sonucu.
        shap_explanation: SHAP açıklaması (SHAPExplainer.explain_single çıktısı).

    Returns:
        Gemini'ye gönderilecek kullanıcı mesajı.
    """
    # Aktif öneriler
    active_labels = [
        LABEL_DISPLAY_NAMES[label]
        for label in LABEL_NAMES
        if getattr(prediction.labels, label)
    ]

    inactive_labels = [
        LABEL_DISPLAY_NAMES[label]
        for label in LABEL_NAMES
        if not getattr(prediction.labels, label)
    ]

    prompt_lines = [
        "Hastanın mevcut klinik verileri doğrultusunda aşağıdaki yönlendirme kararları alınmıştır:\n",
    ]

    # Aktif öneriler
    if active_labels:
        prompt_lines.append(f"ÖNERİLEN BİRİMLER: {', '.join(active_labels)}")
    else:
        prompt_lines.append("ÖNERİLEN BİRİM: Hiçbir birime sevk önerilmiyor.")

    # Pasif öneriler
    if inactive_labels:
        prompt_lines.append(f"ÖNERİLMEYEN BİRİMLER: {', '.join(inactive_labels)}\n")

    # Her aktif label için SHAP faktörleri
    prompt_lines.append("KARAR GEREKÇELERİ:")
    for label in LABEL_NAMES:
        if not getattr(prediction.labels, label):
            continue

        if label not in shap_explanation:
            continue

        factors = shap_explanation[label]["top_faktorler"][:3]
        prompt_lines.append(
            f"\nÖNERİ: {LABEL_DISPLAY_NAMES[label]}\nKLİNİK GEREKÇELER:"
        )
        for f in factors:
            prompt_lines.append(f"  - {f['ozellik']}")

    # Pasif label için kısa not
    for label in LABEL_NAMES:
        if getattr(prediction.labels, label):
            continue
        prompt_lines.append(
            f"\n{LABEL_DISPLAY_NAMES[label]} konsültasyonu şu aşamada öncelikli görülmemiştir."
        )

    prompt_lines.append(
        "\nLütfen yukarıdaki kararları, her biri için ayrı paragraflar oluşturarak, "
        "tıbbi derinlikte, akıcı ve doğal bir klinik dille hekime açıkla. "
        "Her karar için patofizyolojik gerekçeyi, hastanın bireysel bulgularıyla ilişkisini "
        "ve klinik aciliyeti belirt. Metin kapsamlı olmalı, maddeli liste kullanılmamalıdır. "
        "CEVABINI SADECE JSON OLARAK VER."
    )
    return "\n".join(prompt_lines)


def build_fallback_explanation(prediction: PredictionResult) -> str:
    """
    LLM erişilemez olduğunda şablon tabanlı açıklama üret.
    API key yoksa veya bağlantı sorunu olduğunda kullanılır.
    """
    active = [
        LABEL_DISPLAY_NAMES[label]
        for label in LABEL_NAMES
        if getattr(prediction.labels, label)
    ]

    if not active:
        return (
            "Klinik karar destek sistemi mevcut parametreler dahilinde "
            "herhangi bir birime sevk önermemektedir. "
            "Klinisyen değerlendirmesi gereklidir."
        )

    lines = [
        f"Klinik karar destek sistemi şu birimlere yönlendirme önermektedir: "
        f"{', '.join(active)}.",
        "",
    ]

    for label in LABEL_NAMES:
        if not getattr(prediction.labels, label):
            continue
        prob = prediction.probabilities[label]
        lines.append(
            f"• {LABEL_DISPLAY_NAMES[label]}: Güven skoru %{prob * 100:.0f}."
        )

    lines.append("")
    lines.append(
        "Detaylı gerekçe için SHAP analiz grafiğini inceleyiniz. "
        "Tüm kararlar klinisyen değerlendirmesi ile desteklenmelidir."
    )

    return "\n".join(lines)


# ─── LLM Servisi ──────────────────────────────────────────────────────────────

class LLMExplainer:
    """
    Gemini API ile ML kararlarını açıklayan servis.

    api_key boşsa veya llm_enabled=False ise fallback template kullanılır.
    """

    def __init__(
        self,
        api_key: str = "",
        enabled: bool = True,
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ):
        self.enabled = enabled and bool(api_key)
        self._model = None

        if self.enabled:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._model = genai.GenerativeModel(
                    model_name="gemini-3.5-flash",
                    system_instruction=SYSTEM_PROMPT,
                    generation_config=genai.GenerationConfig(
                        temperature=temperature,
                        top_p=0.9,
                    ),
                )
                print("[LLM] Gemini Flash bağlantısı hazır.")
            except Exception as e:
                print(f"[LLM] Bağlantı kurulamadı: {e}. Fallback modu aktif.")
                self.enabled = False
        else:
            print("[LLM] Devre dışı. Fallback template kullanılacak.")

    def explain(
        self,
        prediction: PredictionResult,
        shap_explanation: dict,
    ) -> tuple[str, str, bool]:
        """
        ML kararını detaylı epikriz ve kısa özet olarak Türkçeye çevir.

        Args:
            prediction: ML tahmin sonucu.
            shap_explanation: SHAP açıklama sözlüğü.

        Returns:
            (detayli_epikriz, kisa_ozet, fallback_kullanildi_mi)
        """
        if not self.enabled or self._model is None:
            return build_fallback_explanation(prediction), "", True

        try:
            import json
            prompt = build_explanation_prompt(prediction, shap_explanation)
            response = self._model.generate_content(prompt)
            raw = response.text.strip()

            # Gemini bazen ```json ... ``` bloğu içine sarabilir, temizle
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            parsed = json.loads(raw)
            detayli = parsed.get("detayli_epikriz", "").strip()
            ozet = parsed.get("kisa_ozet", "").strip()
            return detayli, ozet, False

        except Exception as e:
            print(f"[LLM] Açıklama üretilirken hata: {e}. Fallback kullanılıyor.")
            fallback = build_fallback_explanation(prediction)
            return fallback, "", True

    @classmethod
    def from_settings(cls) -> "LLMExplainer":
        """settings.py'den otomatik yapılandır."""
        return cls(
            api_key=settings.gemini_api_key,
            enabled=settings.llm_enabled,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
