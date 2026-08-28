"""
LLM Açıklama Servisi
====================
Gemini API kullanarak ML kararını doktor dostu Türkçe'ye çevirir.

KRİTİK: LLM karar VERMİYOR — sadece ML kararını AÇIKLIYOR.
Tüm klinik kararlar XGBoost modeli tarafından üretilir.
LLM sadece bu kararı insan diline çevirir.

Kullanım:
    explainer = LLMExplainer(api_key=settings.gemini_api_key)
    text = explainer.explain(prediction_result, shap_explanation)
"""

from __future__ import annotations

from config.settings import settings, LABEL_NAMES, LABEL_DISPLAY_NAMES
from models.predictor import PredictionResult

# ─── Prompt Şablonları ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sen bir klinik karar destek sisteminin açıklama modülüsün.
Sana bir psoriazis hastası için makine öğrenmesi modelinin verdiği kararlar
ve bu kararları etkileyen faktörler (SHAP değerleri) verilecek.

Görevin: Bu kararları bir dermatoloji uzmanının anlayabileceği, net,
profesyonel ve klinik bir Türkçe ile detaylıca açıklamak.

ZORUNLU KURALLAR:
1. Kesinlikle hastalık tanısı uydurma veya ilaç ismi önerme. Sadece verilen sevk/karar sonuçlarını kullan.
2. Basit listeler (madde imleri) yapmak yerine, kararları profesyonel klinik paragraflar halinde sun.
3. Sana verilen faktörlerin (örn. DLQI yüksekliği, PASI skoru, yaş, LDL) tıbbi olarak ne anlama geldiğini ve kararı neden etkilediğini "nedensellik" kurarak açıkla. Örneğin: 'DLQI skorunun yüksekliği hastanın yaşam kalitesinin ciddi şekilde bozulduğunu gösterdiğinden karar sistemik tedavi yönünde ağır basmıştır' gibi cümleler kur.
4. Cümlelerine "Klinik karar destek sistemi şunları belirledi:" gibi mekanik girişler yapabilirsin.
5. Doktora karşı meslektaş gibi (kollegiyal) ama saygılı bir dil kullan.
6. Sistemi kararın sahibi olarak göster, kendini değil."""


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
        "Hasta verileri analiz edildi. Aşağıdaki klinik karar önerisi üretildi:\n",
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
        prob = prediction.probabilities[label]
        prompt_lines.append(
            f"\n{LABEL_DISPLAY_NAMES[label]} (güven: %{prob * 100:.0f}):"
        )
        for f in factors:
            prompt_lines.append(f"  - {f['ozellik']}: {f['etki']}")

    # Pasif label için de kısa not
    for label in LABEL_NAMES:
        if getattr(prediction.labels, label):
            continue
        prob = prediction.probabilities[label]
        # Negatif karardaki güven = 1 - pozitif sınıf olasılığı
        guven = (1 - prob) * 100
        prompt_lines.append(
            f"\n{LABEL_DISPLAY_NAMES[label]} önerilmedi (güven: %{guven:.0f})."
        )

    prompt_lines.append("\nLütfen bu kararı doktora net ve mesleki bir dille açıkla:")
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
            f"• {LABEL_DISPLAY_NAMES[label]}: Model güven skoru %{prob * 100:.0f}."
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
        max_tokens: int = 400,
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
    ) -> tuple[str, bool]:
        """
        ML kararını doktor dostu Türkçe'ye çevir.

        Args:
            prediction: ML tahmin sonucu.
            shap_explanation: SHAP açıklama sözlüğü.

        Returns:
            (Türkçe açıklama metni, fallback_kullanildi_mi)
        """
        if not self.enabled or self._model is None:
            return build_fallback_explanation(prediction), True

        try:
            prompt = build_explanation_prompt(prediction, shap_explanation)
            response = self._model.generate_content(prompt)
            return response.text.strip(), False
        except Exception as e:
            print(f"[LLM] Açıklama üretilirken hata: {e}. Fallback kullanılıyor.")
            return build_fallback_explanation(prediction), True

    @classmethod
    def from_settings(cls) -> "LLMExplainer":
        """settings.py'den otomatik yapılandır."""
        return cls(
            api_key=settings.gemini_api_key,
            enabled=settings.llm_enabled,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
