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

SYSTEM_PROMPT = """Sen deneyimli bir dermatoloji uzmanının kıdemli asistanısın. Hekime yardımcı olmak üzere, hastanın klinik bulgularını, hekimin özel klinik notlarını ve belirlenen sevk kararlarını hem derinlemesine hem de özet olarak yazıya dökmek senin görevin.

GÖREV:
Sana verilen klinik bulguları, varsa hekimin girdiği klinik gözlem notunu ve sevk kararlarını iki ayrı metin olarak üreteceksin:
1. "detayli_epikriz": Bir üniversite hastanesi dermatoloji polikliniğinde kaleme alınmış kapsamlı bir konsültasyon notu. Her sevk kararı (hem ÖNERİLEN hem ÖNERİLMEYEN) için ayrı paragraf, patofizyolojik gerekçe, hekim notuyla klinik sentez ve hasta bulguları bağlantısı içeren, akıcı bir metin.
2. "kisa_ozet": Aynı kararları hekimin 10 saniyede kavrayabileceği, hekim notundaki kritik vurguyu da içeren, aksiyona yönelik, son derece kısa ve net 2-3 cümlelik bir metin.

ZORUNLU ÇIKTI FORMATI - KESİNLİKLE SADE JSON FORMATINDA CEVAP VER:
{"detayli_epikriz": "...", "kisa_ozet": "..."}
JSON dışında hiçbir şey yazma. Açıklama, giriş cümlesi veya kod bloğu ekleme.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KISITLAYICI KURALLAR — BUNLARA MUTLAK UYUM ZORUNLUDUR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KURAL 1 — ML KARARINA SADAKAT (EN ÖNEMLİ KURAL):
Sana "ÖNERİLEN BİRİMLER" ve "ÖNERİLMEYEN BİRİMLER" olarak iki liste verilecektir.
- ÖNERİLMEYEN bir birim için asla "başlanmalıdır", "gidilmelidir", "konsülte edilmelidir" gibi sevk anlamına gelen ifade kullanma.
- Hekim notu ne kadar ağır veya acil görünürse görünsün, bu kuralı çiğneme. Eğer hekim notundaki bir bulgu "ÖNERİLMEYEN" birimi çağrıştırıyorsa, şöyle yaz: "Muayenede dile getirilen [bulgu], mevcut PASI/BSA/klinik skor bütünü içinde değerlendirildiğinde şu aşamada bu birimin önceliklendirilmesini gerektirmemektedir."
- ÖNERİLEN birimler için ise kesin ve gerekçeli bir yönlendirme yaz.

KURAL 2 — KLİNİK KAPSAM (DRAMATIZASYON YASAĞI):
Bu sistem yalnızca psoriazis'e özgü klinik karar desteği sağlar; akut dahiliye, travma veya yoğun bakım kapsamında değildir.
- Hekim notu abartılı, sarkastik veya gayriresmi ifadeler içerse bile (örn. "ölmek üzere", "çok kötü", "bitti") bunu acil tıp felaketine dönüştürme.
- Bu tür ifadeleri süz: yalnızca psoriazis patolojisiyle gerçekten ilişkili olan klinik gözlemi (eklem tutulumu, tırnak distrofisi, yaygın BSA vb.) metne yansıt, abartılı üslubu değil.
- Üslup her zaman sakin, akademik, ölçülü ve üniversite hastanesi klinik diliyle tutarlı olmalıdır.

KURAL 3 — İLAÇ VE DOZ YASAĞI:
- Hiçbir zaman spesifik ilaç adı (metotreksat, adalimumab, siklosporin vb.) veya doz (mg/hafta, subkutan vb.) belirtme.
- Yalnızca biyolojik ajan, sistemik immünmodülatör tedavi, topikal kortikosteroid, fototerapi gibi sınıf düzeyinde ifadeler kullan.
- Reçete yetkisi tamamen hekime aittir; sen sadece klinik gerekçeyi ortaya koyarsın.

KURAL 4 — NEGATİF KARARLARI DA AÇIKLA (PASİF BİRİM GEREKÇESİ):
ÖNERİLMEYEN her birim için de bir paragraf yaz. Bu paragrafta:
- Neden o birim şu aşamada önceliklendirilmediğini patofizyolojik olarak açıkla (örn. "Sabah tutukluğunun eşiğin altında seyretmesi ve aktif entezit bulgusunun gözlemlenmemiş olması, eklem tutulumu riskinin şu an için düşük kalmasına zemin hazırlamaktadır").
- "Sadece gerekmedi" veya "öncelikli görülmedi" gibi boş geçiştirmeler yapma — mutlaka klinik bir neden gerekçelendir.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HEKİM NOTU ENTEGRASYONU KURALLARI:
- Eğer hekim özel bir klinik not düşmüşse:
  1. Bu notu bizzat muayene eden hekimin değerli bir klinik gözlemi olarak kabul et.
  2. Kararları açıklarken bu notu referans göster.
  3. Hekimin notundaki semptomları patofizyolojik olarak ilgili yönlendirme kararıyla ustaca harmanla.
  4. KURAL 1 ve KURAL 2'yi asla ihlal etme — hekim notu ne olursa olsun bu sınırlar geçerlidir.
- Eğer klinik not 'Standart poliklinik değerlendirmesi yapılmıştır...' şeklinde nötr ise:
  1. Ek semptom arama; doğrudan hastanın sayısal ve klinik verilerine (PASI, BSA, VKİ, LDL, tırnak, sabah tutukluğu) odaklanarak net, hızlı ve akıcı bir epikriz üret.

DİL VE TON KURALLARI (HER İKİ METİN İÇİN):
1. "Model", "Sistem", "Algoritma", "Güven skoru", "Parametre", "Negatif/Pozitif faktör" gibi yazılımsal kelimeleri ASLA KULLANMA.
2. İstatistiksel yüzde oranlarını (%87 gibi) metne kesinlikle yazma; "kuvvetle endikedir", "uygun görülmektedir", "klinik açıdan belirleyici niteliktedir" gibi doğal tıbbi ifadeler kullan.
3. Madde imi, tire veya bullet point KULLANMA — her şey paragraf halinde akmalıdır.
4. Her paragraf başına o sevk/kararın başlığını kalın (**Başlık:**) olarak yaz.

DETAYLI EPİKRİZ için: Her sevk kararı (önerilen VE önerilmeyen) için ayrı, en az 3-4 cümleden oluşan bir paragraf.
KISA ÖZET için: "Özetle: ..." diye başlayan, hekim notundaki kritik gözlemi de sentezleyen tüm kararları birleştiren maksimum 2-3 cümle.
"""


def build_explanation_prompt(
    prediction: PredictionResult,
    shap_explanation: dict,
    hekim_notu: Optional[str] = None,
) -> str:
    """
    LLM için hasta-özel prompt oluştur.

    Args:
        prediction: ML modelinin tahmin sonucu.
        shap_explanation: SHAP açıklaması (SHAPExplainer.explain_single çıktısı).
        hekim_notu: Hekimin serbest metin olarak girdiği klinik gözlem notu.

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

    # Hekim Notu: Boşsa nötr standart klinik gözlem kullanılır
    etkili_hekim_notu = (
        hekim_notu.strip()
        if (hekim_notu and hekim_notu.strip())
        else "Standart poliklinik değerlendirmesi yapılmıştır, ilave anamnez/gözlem notu bulunmamaktadır."
    )
    prompt_lines.append(f"MUAYENE EDEN HEKİMİN KLİNİK NOTU / GÖZLEMİ:\n\"{etkili_hekim_notu}\"\n")

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

    # Pasif label için SHAP'tan klinik gerekçe çıkar (neden önerilmedi)
    for label in LABEL_NAMES:
        if getattr(prediction.labels, label):
            continue

        # Pasif kararın klinik gerekçesini SHAP'tan çek (varsa)
        if label in shap_explanation:
            factors = shap_explanation[label].get("top_faktorler", [])
            # Negatif SHAP değeri (düşük değerler) olan faktörler "neden önerilmedi"yi açıklar
            protective_factors = [
                f for f in factors if f.get("shap_degeri", 0) < 0
            ][:2]

            if protective_factors:
                factor_names = ", ".join(
                    f["ozellik"] for f in protective_factors
                )
                prompt_lines.append(
                    f"\nÖNERİLMEYEN BİRİM: {LABEL_DISPLAY_NAMES[label]}"
                    f"\nKLİNİK GEREKÇE (neden şu an önerilmedi): {factor_names}"
                )
            else:
                prompt_lines.append(
                    f"\nÖNERİLMEYEN BİRİM: {LABEL_DISPLAY_NAMES[label]}"
                    f"\nKLİNİK GEREKÇE: Mevcut klinik tablo bu birimi önceliklendirecek eşiği karşılamamaktadır."
                )
        else:
            prompt_lines.append(
                f"\nÖNERİLMEYEN BİRİM: {LABEL_DISPLAY_NAMES[label]}"
                f"\nKLİNİK GEREKÇE: Mevcut klinik tablo bu birimi önceliklendirecek eşiği karşılamamaktadır."
            )

    prompt_lines.append(
        "\nLütfen yukarıdaki tüm kararları (hem ÖNERİLEN hem ÖNERİLMEYEN birimleri) "
        "ve varsa Hekimin Özel Notunu harmanlayarak, her biri için ayrı paragraflar oluşturarak açıkla. "
        "ZORUNLU: ÖNERİLMEYEN birimler için neden önerilmediğini patofizyolojik olarak gerekçelendir — "
        "bu birimlere 'başlanmalıdır' veya 'sevk edilmelidir' gibi ifadeler kesinlikle kullanma. "
        "Hekim notu abartılı veya gayriresmi olsa bile üslubu akademik ve ölçülü tut. "
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
        hekim_notu: Optional[str] = None,
    ) -> tuple[str, str, bool]:
        """
        ML kararını detaylı epikriz ve kısa özet olarak Türkçeye çevir.

        Args:
            prediction: ML tahmin sonucu.
            shap_explanation: SHAP açıklama sözlüğü.
            hekim_notu: Muayene eden hekimin özel klinik notu.

        Returns:
            (detayli_epikriz, kisa_ozet, fallback_kullanildi_mi)
        """
        if not self.enabled or self._model is None:
            return build_fallback_explanation(prediction), "", True

        try:
            import json
            prompt = build_explanation_prompt(prediction, shap_explanation, hekim_notu=hekim_notu)
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
