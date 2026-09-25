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

from typing import Optional

from config.settings import settings, LABEL_NAMES, LABEL_DISPLAY_NAMES
from models.predictor import PredictionResult
from llm.guidelines_kb import GuidelinesKnowledgeBase, guidelines_kb

# ─── Prompt Şablonları ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sen Türk Dermatoloji Derneği ve Avrupa Dermatoloji Forumu'nun 2025 yılı güncel kılavuzlarına hâkim, deneyimli bir dermatoloji uzmanının kıdemli asistanısın. Hekime yardımcı olmak üzere, hastanın klinik bulgularını, hekimin özel klinik notlarını ve belirlenen sevk kararlarını hem derinlemesine hem de özet olarak yazıya dökmek senin görevin.

KLİNİK OTORİTE ÇERÇEVEN:
Sana verilen klinik dayanak bloğunda yer alan iki resmi kaynak senin bilgi temelin olarak kullanılacaktır:
- Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD) — ulusal konsensüs rehberi
- EuroGuiDerm 2025 — Avrupa Dermatoloji Forumu sistematik tedavi kılavuzu
Bu kaynakları epikrizinde doğal klinik dille referans gösterebilirsin. Örnek ifadeler:
  "Türkiye Psoriasis Kılavuzu 2025 uyarınca..."
  "EuroGuiDerm 2025 kriterleri çerçevesinde..."
  "Güncel ulusal kılavuz ölçütlerine göre..."
Kaynak adını parantez içinde vermek yeterlidir; sayfa numarası veya DOI yazmana gerek yoktur.

GÖREV:
Sana verilen klinik bulguları, varsa hekimin girdiği klinik gözlem notunu ve sevk kararlarını iki ayrı metin olarak üreteceksin:
1. "detayli_epikriz": Bir üniversite hastanesi dermatoloji polikliniğinde kaleme alınmış kapsamlı bir konsültasyon notu. Her sevk kararı (hem ÖNERİLEN hem ÖNERİLMEYEN) için ayrı paragraf, patofizyolojik gerekçe, 2025 kılavuz dayanağı, hekim notuyla klinik sentez ve hasta bulguları bağlantısı içeren, akıcı bir metin.
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
- Neden o birim şu aşamada önceliklendirilmediğini patofizyolojik olarak açıkla.
- "Sadece gerekmedi" veya "öncelikli görülmedi" gibi boş geçiştirmeler yapma — mutlaka klinik bir neden gerekçelendir.

KURAL 5 — KILAVUZ ATIFLARINI DOĞAL KULLAN:
Sana verilen "KLİNİK DAYANAK" bloğundaki bilgileri epikrizde doğal biçimde harmanlayarak kullan.
- Her paragrafta kılavuz atfı yapmak zorunda değilsin; ama özellikle eşik değerleri (PASI > 10, DLQI > 10, VKİ > 30 vb.) ve sevk kararlarını gerekçelendirirken kılavuz referansı ver.
- Atıfları mekanik kopya-yapıştır olarak değil, klinik bağlamla sentezlemiş şekilde kullan.

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
    # Hasta parametreleri — kılavuz atıf seçimi için
    pasi: Optional[float] = None,
    bsa: Optional[float] = None,
    dlqi: Optional[float] = None,
    vki: Optional[float] = None,
    ldl: Optional[float] = None,
    tirnak_tutulumu: bool = False,
    sabah_turuklugu: bool = False,
    eklem_bulgulari: Optional[bool] = None,
    sigara: bool = False,
) -> str:
    """
    LLM için hasta-özel, kılavuz destekli prompt oluştur.

    Yenilik (2025 Kılavuz Entegrasyonu):
        Hasta parametrelerine ve aktif ML kararlarına göre, guidelines_kb'den
        ilgili resmi atıflar seçilir ve prompt'a "KLİNİK DAYANAK" bloğu
        olarak enjekte edilir. LLM bu atıfları doğal klinik dille epikrizde kullanır.

    Args:
        prediction:         ML modelinin tahmin sonucu.
        shap_explanation:   SHAP açıklaması (SHAPExplainer.explain_single çıktısı).
        hekim_notu:         Hekimin serbest metin olarak girdiği klinik gözlem notu.
        pasi, bsa, dlqi, vki, ldl, tirnak_tutulumu, sabah_turuklugu,
        eklem_bulgulari, sigara: Hasta klinik parametreleri — kılavuz
                            atıflarını kişiselleştirmek için kullanılır.

    Returns:
        Gemini'ye gönderilecek kullanıcı mesajı (kılavuz atıflarıyla zenginleştirilmiş).
    """
    # ── Kılavuz Atıflarını Seç ────────────────────────────────────────────────
    secilen_atiflar = guidelines_kb.get_relevant_citations(
        ftr_karari=prediction.labels.ftr,
        sistemik_karari=prediction.labels.sistemik_tedavi,
        aile_hek_karari=prediction.labels.aile_hekimligi,
        pasi=pasi,
        bsa=bsa,
        dlqi=dlqi,
        vki=vki,
        ldl=ldl,
        tirnak_tutulumu=tirnak_tutulumu,
        sabah_turuklugu=sabah_turuklugu,
        eklem_bulgulari=eklem_bulgulari,
        sigara=sigara,
    )
    kilavuz_blogu = guidelines_kb.format_for_prompt(secilen_atiflar)

    # ── Aktif / Pasif Kararlar ────────────────────────────────────────────────
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

    # ── Hekim Notu ────────────────────────────────────────────────────────────
    etkili_hekim_notu = (
        hekim_notu.strip()
        if (hekim_notu and hekim_notu.strip())
        else "Standart poliklinik değerlendirmesi yapılmıştır, ilave anamnez/gözlem notu bulunmamaktadır."
    )
    prompt_lines.append(f"MUAYENE EDEN HEKİMİN KLİNİK NOTU / GÖZLEMİ:\n\"{etkili_hekim_notu}\"\n")

    # ── Karar Özetleri ────────────────────────────────────────────────────────
    if active_labels:
        prompt_lines.append(f"ÖNERİLEN BİRİMLER: {', '.join(active_labels)}")
    else:
        prompt_lines.append("ÖNERİLEN BİRİM: Hiçbir birime sevk önerilmiyor.")

    if inactive_labels:
        prompt_lines.append(f"ÖNERİLMEYEN BİRİMLER: {', '.join(inactive_labels)}\n")

    # ── SHAP Gerekçeleri (Aktif Kararlar) ─────────────────────────────────────
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

    # ── SHAP Gerekçeleri (Pasif Kararlar — Neden Önerilmedi) ─────────────────
    for label in LABEL_NAMES:
        if getattr(prediction.labels, label):
            continue

        if label in shap_explanation:
            factors = shap_explanation[label].get("top_faktorler", [])
            protective_factors = [
                f for f in factors if f.get("shap_degeri", 0) < 0
            ][:2]

            if protective_factors:
                factor_names = ", ".join(f["ozellik"] for f in protective_factors)
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

    # ── Kılavuz Atıf Bloğu ────────────────────────────────────────────────────
    if kilavuz_blogu:
        prompt_lines.append(f"\n{kilavuz_blogu}")

    # ── Final Direktifi ───────────────────────────────────────────────────────
    prompt_lines.append(
        "\nLütfen yukarıdaki tüm kararları (hem ÖNERİLEN hem ÖNERİLMEYEN birimleri), "
        "Hekimin Özel Notunu ve KLİNİK DAYANAK bloğundaki kılavuz atıflarını harmanlayarak, "
        "her biri için ayrı paragraflar oluşturarak açıkla. "
        "ZORUNLU: ÖNERİLMEYEN birimler için neden önerilmediğini patofizyolojik olarak gerekçelendir — "
        "bu birimlere 'başlanmalıdır' veya 'sevk edilmelidir' gibi ifadeler kesinlikle kullanma. "
        "Kılavuz atıflarını doğal klinik dille ve seçici olarak kullan. "
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
        max_tokens: int = 4000,
        model_name: str = "gemini-3.1-flash-lite-preview",
    ):
        self.enabled = enabled and bool(api_key)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._models: dict[str, Any] = {}

        # Fallback model listesi (sıralı deneme zinciri)
        raw_models = [model_name, "gemini-3.1-flash-lite", "gemini-3-flash-preview"]
        self._model_names: list[str] = []
        for m in raw_models:
            if m and m not in self._model_names:
                self._model_names.append(m)

        if self.enabled:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                # İlk modeli hemen ısıt
                self._get_model(self._model_names[0])
                print(f"[LLM] Gemini {self._model_names[0]} bağlantısı hazır (zincir: {' → '.join(self._model_names)}).")
            except Exception as e:
                print(f"[LLM] Bağlantı kurulamadı: {e}. Fallback modu aktif.")
                self.enabled = False
        else:
            print("[LLM] Devre dışı. Fallback template kullanılacak.")

    def _get_model(self, m_name: str):
        """Model nesnesini lazy initialize et."""
        if m_name not in self._models:
            import google.generativeai as genai
            self._models[m_name] = genai.GenerativeModel(
                model_name=m_name,
                system_instruction=SYSTEM_PROMPT,
                generation_config=genai.GenerationConfig(
                    temperature=self.temperature,
                    top_p=0.9,
                    max_output_tokens=self.max_tokens,
                ),
            )
        return self._models[m_name]

    def explain(
        self,
        prediction: PredictionResult,
        shap_explanation: dict,
        hekim_notu: Optional[str] = None,
        # Hasta parametreleri — kılavuz atıf seçimi için
        pasi: Optional[float] = None,
        bsa: Optional[float] = None,
        dlqi: Optional[float] = None,
        vki: Optional[float] = None,
        ldl: Optional[float] = None,
        tirnak_tutulumu: bool = False,
        sabah_turuklugu: bool = False,
        eklem_bulgulari: Optional[bool] = None,
        sigara: bool = False,
    ) -> tuple[str, str, bool, list[str]]:
        """
        ML kararını detaylı epikriz ve kısa özet olarak Türkçeye çevir.
        2025 kılavuz atıflarını kapsayan zenginleştirilmiş versiyon.

        Args:
            prediction:       ML tahmin sonucu.
            shap_explanation: SHAP açıklama sözlüğü.
            hekim_notu:       Muayene eden hekimin özel klinik notu.
            pasi, bsa, dlqi, vki, ldl, tirnak_tutulumu, sabah_turuklugu,
            eklem_bulgulari, sigara: Kılavuz atıf seçimi için hasta parametreleri.

        Returns:
            (detayli_epikriz, kisa_ozet, fallback_kullanildi_mi, kilavuz_atiflar)
            kilavuz_atiflar: API yanıtına ve PDF'e eklenecek atıf listesi.
        """
        # Kılavuz atıflarını her durumda (fallback dahil) hesapla
        secilen_atiflar = guidelines_kb.get_relevant_citations(
            ftr_karari=prediction.labels.ftr,
            sistemik_karari=prediction.labels.sistemik_tedavi,
            aile_hek_karari=prediction.labels.aile_hekimligi,
            pasi=pasi, bsa=bsa, dlqi=dlqi, vki=vki, ldl=ldl,
            tirnak_tutulumu=tirnak_tutulumu,
            sabah_turuklugu=sabah_turuklugu,
            eklem_bulgulari=eklem_bulgulari,
            sigara=sigara,
        )
        kilavuz_atiflar = guidelines_kb.format_citations_for_api(secilen_atiflar)

        if not self.enabled or not self._model_names:
            return build_fallback_explanation(prediction), "", True, kilavuz_atiflar

        try:
            import json
            import re

            prompt = build_explanation_prompt(
                prediction, shap_explanation,
                hekim_notu=hekim_notu,
                pasi=pasi, bsa=bsa, dlqi=dlqi, vki=vki, ldl=ldl,
                tirnak_tutulumu=tirnak_tutulumu,
                sabah_turuklugu=sabah_turuklugu,
                eklem_bulgulari=eklem_bulgulari,
                sigara=sigara,
            )

            raw = ""
            last_err = None
            for m_name in self._model_names:
                try:
                    m = self._get_model(m_name)
                    response = m.generate_content(
                        prompt,
                        request_options={"timeout": 15.0},
                    )
                    raw = response.text.strip()
                    if raw:
                        last_err = None
                        break
                except Exception as ex:
                    last_err = ex
                    print(f"[LLM] Model {m_name} çağrısı başarısız ({ex}). Sıradaki model deneniyor...")
                    continue

            if not raw:
                print(f"[LLM] Tüm modeller yanıt veremedi (Son hata: {last_err}). Fallback devrede.")
                return build_fallback_explanation(prediction), "", True, kilavuz_atiflar

            # ── Katman 1: Markdown kod bloklarını temizle ─────────────────────
            clean_raw = raw
            if "```" in clean_raw:
                block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_raw, re.DOTALL)
                if block_match:
                    clean_raw = block_match.group(1)
                else:
                    parts = clean_raw.split("```")
                    for part in parts:
                        part = part.strip()
                        if part.startswith("json"):
                            part = part[4:].strip()
                        if part.startswith("{") and part.endswith("}"):
                            clean_raw = part
                            break

            parsed = None

            # ── Katman 2: Standart JSON parse (strict=False — kontrol karakterlerini tolere eder) ──
            try:
                parsed = json.loads(clean_raw, strict=False)
            except Exception as json_err:
                print(f"[LLM] JSON parse uyarısı: {json_err}. Akıllı kurtarma deneniyor...")

                # ── Katman 3: Regex kurtarma — detayli_epikriz ───────────────
                # Türkçe klinik metinde iç tırnak veya kesim olduğunda regex ile kurtarma
                detayli_match = re.search(
                    r'"detayli_epikriz"\s*:\s*"(.*?)(?:"\s*,\s*"kisa_ozet"|\s*"\s*\}|\Z)',
                    clean_raw, re.DOTALL
                )
                ozet_match = re.search(
                    r'"kisa_ozet"\s*:\s*"(.*?)(?:"\s*\}|\Z)',
                    clean_raw, re.DOTALL
                )

                if detayli_match or ozet_match:
                    def safe_unescape(s: str) -> str:
                        s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
                        s = s.replace(r'\"', '"').replace(r"\n", "\n").replace(r"\t", "\t")
                        return s

                    parsed = {
                        "detayli_epikriz": safe_unescape(detayli_match.group(1).rstrip('"')).strip() if detayli_match else "",
                        "kisa_ozet": safe_unescape(ozet_match.group(1).rstrip('"')).strip() if ozet_match else "",
                    }
                    print("[LLM] Regex kurtarma başarılı.")
                else:
                    # ── Katman 4: Ham metin — en azından bir şey göster ──────
                    # JSON tamamen parse edilemiyorsa ham metni detaylı epikriz olarak sun
                    parsed = {
                        "detayli_epikriz": clean_raw.replace('{"detayli_epikriz":', "").replace('"}', "").strip(),
                        "kisa_ozet": "",
                    }
                    print("[LLM] Ham metin kurtarma uygulandı.")

            detayli = parsed.get("detayli_epikriz", "").strip() if parsed else ""
            ozet = parsed.get("kisa_ozet", "").strip() if parsed else ""
            return detayli, ozet, False, kilavuz_atiflar

        except Exception as e:
            print(f"[LLM] Açıklama üretilirken hata: {e}. Fallback kullanılıyor.")
            fallback = build_fallback_explanation(prediction)
            return fallback, "", True, kilavuz_atiflar

    @classmethod
    def from_settings(cls) -> "LLMExplainer":
        """settings.py'den otomatik yapılandır."""
        return cls(
            api_key=settings.gemini_api_key,
            enabled=settings.llm_enabled,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            model_name=getattr(settings, "llm_model", "gemini-3.1-flash-lite-preview"),
        )
