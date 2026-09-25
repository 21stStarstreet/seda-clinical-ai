"""
Soru-Cevap Motoru (QA Engine).
Retrieval sonuçları + Gemini → yapılandırılmış Türkçe klinik cevap.

Bu modülün En Kritik Parçası: SYSTEM PROMPT.
    Kötü bir system prompt, RAG'ı anlamsız hale getirir.
    LLM ya bağlamın dışına çıkarak hallüsinasyon üretir (çok gevşek),
    ya da bağlamda açıkça yazılı şeyleri dahi söylemekten kaçınır (çok katı).
    Doğru denge: "SADECE bu bağlamdan cevap ver, ama cevabı kendi kelimelerinle yaz."
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai

from rag.config import QA_MODEL, QA_MODEL_FALLBACKS, QA_TEMPERATURE, QA_MAX_OUTPUT_TOKENS, QA_TIMEOUT_SEC
from rag.retriever import RetrievalResponse, RetrievalResult
from config.settings import settings

logger = logging.getLogger(__name__)


def _safe_unescape_json_string(s: str) -> str:
    """
    JSON string içeriğindeki kaçış karakterlerini UTF-8 karakterleri bozmadan açar.
    unicode_escape codec'i UTF-8 byte'larını Latin-1 gibi algılayıp Türkçe karakterleri
    (ö, ü, ş, ı, ğ, ç) bozduğu için elle güvenli unescape yapılır.
    """
    def replace_unicode(m):
        try:
            return chr(int(m.group(1), 16))
        except Exception:
            return m.group(0)

    # 1. \\uXXXX Unicode kaçışları
    s = re.sub(r"\\u([0-9a-fA-F]{4})", replace_unicode, s)
    # 2. Standart JSON kaçış karakterleri
    s = s.replace(r'\"', '"')
    s = s.replace(r"\\", "\\")
    s = s.replace(r"\/", "/")
    s = s.replace(r"\n", "\n")
    s = s.replace(r"\r", "\r")
    s = s.replace(r"\t", "\t")
    return s


# ─── Sistem Promptu (Değiştirilmeden Önce Çok Dikkatli Düşün) ────────────────

_SYSTEM_PROMPT = """Sen Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD) ve EuroGuiDerm 2025 kılavuzlarına hâkim üst düzey bir klinik kılavuz danışmanısın. Hekimlere ve araştırmacılara güncel kılavuz bilgilerini sentezleyerek güvenilir klinik rehberlik sunarsın.

TEMEL PRENSİPLER:

0. KLİNİK OLMAYAN GİRDİ REDDİ (En Yüksek Öncelik):
Eğer GÜNCEL SORU aşağıdaki kategorilerden birine giriyorsa, "bulunamadi": true ve "cevap": null döndür — hiçbir klinik bilgi ekleme:
  - Anlamsız/saçma metin (ör: "Haha!", "hehe", "ahahaha", "asdfjkl", "!!!")
  - Selamlama veya gündelik konuşma (ör: "merhaba", "nasılsın", "teşekkürler", "tamam")
  - Klinik bağlamla hiçbir ilişkisi olmayan ifadeler
Bu durumda "ret_nedeni" alanını da doldur.

1. KANITA DAYALI VE BAĞLAM ODAKLI:
Sana verilen BAĞLAM bloğundaki kılavuz pasajlarını temel alarak soruyu doğrudan, kapsamlı ve doyurucu şekilde yanıtla. Bağlamdaki klinik mantığı (tanı kriterleri, sevk durumları, tedavi basamakları, takip aralıkları) hekime profesyonelce açıkla.

2. İLAÇ VE TEDAVİ BİLGİSİ:
Kılavuzda geçen tedavi seçeneklerini, etken madde isimlerini (metotreksat, siklosporin, asitretin, anti-TNF, anti-IL17, anti-IL23, JAK vb.) ve kılavuzun öneri derecelerini açıkça belirtebilirsin. Ancak hastaya doğrudan reçete yazmadığını, bu bilgilerin kılavuz özeti olduğunu unutma.

3. KLİNİK SENTEZ VE ANLAYIŞ:
Hekimin sorusu dolaylı bir klinik soru olsa bile (örn: "sabah tutukluğunda ne yapılır?", "sevk kriterleri nelerdir?"), bağlamda psoriatik artrit, eklem tutulumu veya konsültasyon ile ilgili bilgiler varsa bunları sentezleyerek açıkla. Hemen "bulunamadı" deme; bağlamdaki ilgili kılavuz önerilerini hekime sun.

4. BULUNAMADI DURUMU:
Yalnızca ve yalnızca bağlamda soruyla uzaktan yakından hiçbir klinik ilgi yoksa (örn: konu dışı veya kılavuz dışı sorular), o zaman "bulunamadi": true yap.

5. ATIF ZORUNLULUĞU:
Her önemli tespitin yanına kılavuz sayfasını ekle: (TR2025, s.12) veya (EG2025, s.45). Dil daima akademik, akıcı, hekim seviyesinde Türkçe olmalıdır.

ÇIKTI FORMATI — SADECE JSON:
{
  "cevap": "Türkçe klinik cevap metni. Kaynaklar parantez içinde: (TR2025, s.11)",
  "kaynaklar": [
    {
      "kaynak_kodu": "TR2025",
      "display_source": "Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD)",
      "sayfa": 11,
      "bolum": "Bölüm başlığı",
      "alinti": "Kılavuzdan alınan kısa kilit ifade (maks 120 karakter)"
    }
  ],
  "bulunamadi": false,
  "ret_nedeni": null
}

Klinik dışı girdi reddinde:
{
  "cevap": null,
  "kaynaklar": [],
  "bulunamadi": true,
  "ret_nedeni": "Klinik soru değil"
}

Markdown, kod bloğu, açıklama yazma. SADECE JSON."""


# ─── Cevap Veri Yapıları ──────────────────────────────────────────────────────

@dataclass
class SourceReference:
    kaynak_kodu: str
    display_source: str
    sayfa: int
    bolum: str
    alinti: str


@dataclass
class QAResponse:
    """QA Engine'in tam yanıtı."""

    soru: str
    cevap: str
    kaynaklar: list[SourceReference] = field(default_factory=list)
    bulunamadi: bool = False
    fallback_kullanildi: bool = False
    islem_suresi_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "cevap": self.cevap,
            "kaynaklar": [
                {
                    "kaynak_kodu": s.kaynak_kodu,
                    "display_source": s.display_source,
                    "sayfa": s.sayfa,
                    "bolum": s.bolum,
                    "alinti": s.alinti,
                }
                for s in self.kaynaklar
            ],
            "bulunamadi": self.bulunamadi,
            "fallback_kullanildi": self.fallback_kullanildi,
            "islem_suresi_ms": round(self.islem_suresi_ms, 1),
        }


# ─── QA Engine ────────────────────────────────────────────────────────────────

class QAEngine:
    """
    Bağlam + Soru → Gemini → Yapılandırılmış Klinik Cevap.

    Model Fallback Zinciri:
        429/hata durumunda QA_MODEL → QA_MODEL_FALLBACKS[0] → ... sırasıyla denenir.
        Her model ayrı kota havuzuna sahiptir; bu sayede tek modelin kotası dolduğunda
        sistem durmaz ve bir sonraki modelden yanıt almaya devam eder.
    """

    def __init__(self) -> None:
        api_key = settings.gemini_api_key
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY ayarlanmamış.")
        genai.configure(api_key=api_key)

        # Tüm model listesi: birincil + fallback'ler
        self._model_names: list[str] = [QA_MODEL] + list(QA_MODEL_FALLBACKS)
        # Her model adı için GenerativeModel nesnesi (lazy init — ilk kullanımda oluşturulur)
        self._models: dict[str, genai.GenerativeModel] = {}
        logger.info(
            "[QAEngine] Hazır. Model zinciri: %s",
            " → ".join(self._model_names),
        )

    def _get_model(self, model_name: str) -> genai.GenerativeModel:
        """Model nesnesini önbellekten döndür veya oluştur."""
        if model_name not in self._models:
            self._models[model_name] = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=_SYSTEM_PROMPT,
                generation_config=genai.GenerationConfig(
                    temperature=QA_TEMPERATURE,
                    max_output_tokens=QA_MAX_OUTPUT_TOKENS,
                    response_mime_type="application/json",
                ),
            )
            logger.debug("[QAEngine] Model nesnesi oluşturuldu: %s", model_name)
        return self._models[model_name]

    def answer(
        self,
        soru: str,
        retrieval: RetrievalResponse,
        islem_suresi_ms: float = 0.0,
        gecmis: Optional[list[dict]] = None,
    ) -> QAResponse:
        """
        Retrieval sonuçlarını + soruyu Gemini'ye gönder, cevabı parse et.

        Model Fallback Zinciri:
            Birincil model 429 verirse bir sonraki modele geçilir.
            Tüm modeller başarısız olursa _fallback() tetiklenir.

        Args:
            soru: Hekimin sorusu (orijinal, preprocessor değiştirmez).
            retrieval: Retriever'dan gelen sonuçlar.
            islem_suresi_ms: Toplam işlem süresini doldurmak için.
            gecmis: Son Q/A çiftleri listesi. Her öğe {"soru": str, "cevap": str}.
                    Opsiyonel — None ise stateless davranış (mevcut gibi).

        Returns:
            QAResponse — cevap, kaynaklar, bulunamadı bayrağı.
        """
        import time
        t0 = time.time()

        # Retrieval başarısız → direkt "bulunamadı"
        if not retrieval.found or not retrieval.hits:
            return QAResponse(
                soru=soru,
                cevap="Bu soruya ilişkin bilgi verilen kılavuz bölümlerinde yer almamaktadır. Lütfen kılavuzun ilgili bölümünü doğrudan inceleyiniz.",
                bulunamadi=True,
                islem_suresi_ms=islem_suresi_ms,
            )

        # Kullanıcı promptunu oluştur (sohbet geçmişi varsa enjekte edilir)
        prompt = self._build_prompt(soru, retrieval, gecmis=gecmis)

        raw = ""
        last_exc: Optional[Exception] = None

        # ─── Model Fallback Zinciri ──────────────────────────────────────────
        # Birincil model → fallback_1 → fallback_2 → ... sırasıyla dene.
        # 429 (kota doldu) durumunda bir sonraki modele geç.
        # Diğer hatalar (4xx, 5xx dışı) → aynı modelde bir kez daha dene sonra geç.
        for model_name in self._model_names:
            model = self._get_model(model_name)
            try:
                response = model.generate_content(
                    prompt,
                    request_options={"timeout": QA_TIMEOUT_SEC},
                )
                raw = response.text.strip()
                logger.info("[QAEngine] Yanıt alındı (model: %s, %d karakter)", model_name, len(raw))
                last_exc = None
                break  # Başarılı → döngüden çık
            except Exception as ex:
                last_exc = ex
                err_str = str(ex).lower()
                is_quota = "429" in err_str or "quota" in err_str or "exhausted" in err_str
                is_unavailable = "503" in err_str or "unavailable" in err_str or "demand" in err_str
                is_timeout = "timeout" in err_str or "deadline" in err_str or "504" in err_str

                reason = (
                    "Kota/429" if is_quota else
                    "Yoğunluk/503" if is_unavailable else
                    "Zaman Aşımı/Timeout" if is_timeout else
                    "Model Hatası"
                )
                logger.warning(
                    "[QAEngine] %s (%s): %s. Bir sonraki modele geçiliyor...",
                    reason, model_name, ex,
                )
                continue

        # Tüm modeller başarısız oldu
        if last_exc is not None:
            logger.error("[QAEngine] Tüm modeller başarısız. Son hata: %s", last_exc)
            return self._fallback(soru, retrieval, islem_suresi_ms)

        if not raw:
            return self._fallback(soru, retrieval, islem_suresi_ms)

        try:
            parsed = None

            # 1. Markdown kod bloklarını temizle (```json ... ``` veya ``` ... ```)
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

            # 2. Standart JSON parse dene
            try:
                # strict=False satır sonu ve kontrol karakterlerini JSON string içinde kabul eder
                parsed = json.loads(clean_raw, strict=False)
            except Exception as json_err:
                logger.warning("[QAEngine] JSON parse uyarısı: %s. Akıllı kurtarma yapılıyor...", json_err)

                # 3. Akıllı Kurtarma (Multi-Strategy Extraction):
                # İç tırnaklar veya kesilmeler olsa bile "cevap" ve "kaynaklar" bloklarını güvenle ayıkla
                recovered_cevap = ""
                cevap_match = re.search(
                    r'"cevap"\s*:\s*"(.*?)(?:"\s*,\s*"(?:kaynaklar|bulunamadi)|\s*"\s*\}|\Z)',
                    clean_raw,
                    re.DOTALL
                )

                if cevap_match:
                    extracted = cevap_match.group(1).rstrip()
                    # Eğer sonundaki kapanış tırnağı ve parantez kalmışsa temizle
                    if extracted.endswith('"'):
                        extracted = extracted[:-1]
                    recovered_cevap = _safe_unescape_json_string(extracted).strip()

                kaynaklar_list = []
                kaynaklar_match = re.search(r'"kaynaklar"\s*:\s*(\[.*?\])', clean_raw, re.DOTALL)
                if kaynaklar_match:
                    try:
                        kaynaklar_list = json.loads(kaynaklar_match.group(1), strict=False)
                    except Exception:
                        pass

                if recovered_cevap:
                    parsed = {
                        "cevap": recovered_cevap,
                        "kaynaklar": kaynaklar_list,
                        "bulunamadi": False,
                    }
                else:
                    # Düz metin olarak gelmişse doğrudan al
                    clean_text = clean_raw.replace("```json", "").replace("```", "").strip()
                    parsed = {
                        "cevap": clean_text,
                        "kaynaklar": kaynaklar_list,
                        "bulunamadi": False,
                    }

            elapsed = (time.time() - t0) * 1000 + islem_suresi_ms

            # Kaynakları çıkar (eğer model kaynak listesi üretmediyse retrieval'dan otomatik tamamla)
            kaynaklar_raw = parsed.get("kaynaklar", [])
            if kaynaklar_raw:
                kaynaklar = [
                    SourceReference(
                        kaynak_kodu=s.get("kaynak_kodu", ""),
                        display_source=s.get("display_source", ""),
                        sayfa=s.get("sayfa", 0),
                        bolum=s.get("bolum", ""),
                        alinti=s.get("alinti", ""),
                    )
                    for s in kaynaklar_raw
                ]
            else:
                # Retrieval hit'lerinden zengin kaynak referansı oluştur
                kaynaklar = [
                    SourceReference(
                        kaynak_kodu=h.source_code,
                        display_source=h.display_source,
                        sayfa=h.doc_page,
                        bolum=h.heading or "Klinik Kılavuz Bölümü",
                        alinti=h.text[:120].strip() + "...",
                    )
                    for h in retrieval.hits[:3]
                ]

            return QAResponse(
                soru=soru,
                cevap=parsed.get("cevap", "").strip(),
                kaynaklar=kaynaklar,
                bulunamadi=parsed.get("bulunamadi", False),
                fallback_kullanildi=False,
                islem_suresi_ms=elapsed,
            )

        except json.JSONDecodeError as exc:
            logger.error("[QAEngine] JSON parse hatası: %s\nRaw: %s", exc, raw[:200])
            return self._fallback(soru, retrieval, islem_suresi_ms)
        except Exception as exc:
            logger.error("[QAEngine] Beklenmeyen hata: %s", exc)
            return self._fallback(soru, retrieval, islem_suresi_ms)

    def _build_prompt(
        self,
        soru: str,
        retrieval: RetrievalResponse,
        gecmis: Optional[list[dict]] = None,
    ) -> str:
        """
        Gemini'ye gönderilecek kullanıcı mesajını oluştur.

        Sohbet geçmişi (gecmis) varsa prompt başına eklenir:
            [SOHBET BAĞLAMI] bloğu → LLM önceki konuyu görür
            [GÜNCEL SORU] → Hekimin bu turda sorduğu soru
            [KILAVUZ BAĞLAMI] → ChromaDB'den gelen ilgili bölümler

        Tasarım kararı: Gecmis olmadığında davranış mevcut ile aynı —
        geriye dönük uyumluluk korunur.
        """
        parts = []

        # 1. Sohbet bağlamı (varsa) — son 1 Q/A çifti yeterli
        if gecmis:
            son_tur = gecmis[-1]  # Sadece son tur — fazlası bağlamı bulanıklaştırır
            onceki_soru = son_tur.get("soru", "")[:300]
            onceki_cevap = son_tur.get("cevap", "")[:500]
            if onceki_soru and onceki_cevap:
                parts.append(
                    f"[SOHBET BAĞLAMI — Bir önceki soru-cevap]\n"
                    f"Önceki Soru: {onceki_soru}\n"
                    f"Önceki Cevap Özeti: {onceki_cevap[:500]}\n"
                )

        # 2. Güncel soru
        parts.append(f"GÜNCEL SORU: {soru}")

        # 3. Kılavuz bağlamı
        parts.append(
            f"\nBAĞLAM (Kılavuzdan alınan ilgili bölümler):\n\n"
            f"{retrieval.context_text}\n\n"
            "Yukarıdaki bağlama dayanarak soruyu yanıtla. "
            "Eğer bağlamda cevap yoksa 'bulunamadi: true' döndür. "
            "SADECE JSON formatında cevap ver."
        )

        return "\n\n".join(parts)

    def _fallback(
        self,
        soru: str,
        retrieval: RetrievalResponse,
        islem_suresi_ms: float,
    ) -> QAResponse:
        """
        Gemini başarısız olursa temiz hata mesajı döndür.

        Tasarım kararı:
            Önceki davranış ham chunk metnini ekrana döküyordu. Bu iki açıdan yanlış:
            1. Chunk konu dışıysa (ör: FTR sorgusu → topikal kortikosteroid sayfası)
               alakasız tıbbi bilgi gösteriliyordu — klinik açıdan tehlikeli.
            2. Fallback metni sohbet geçmişine girince sonraki sorguların
               bağlam füzyonunu zehirliyordu.

            Doğru davranış: LLM başarısız olduğunda her zaman
            "teknik sorun, tekrar dene" mesajı ver. bulunamadi=True yap ki
            DerleGecmis() bu turu sohbet geçmişine katmasın (hedef).
        """
        logger.warning("[QAEngine] Gemini fallback — soru: %r, hit sayısı: %d", soru, len(retrieval.hits))
        return QAResponse(
            soru=soru,
            cevap=(
                "Kılavuz sorgusu şu an yanıt üretemedi. "
                "Lütfen birkaç saniye bekleyip sorunuzu tekrar sorun. "
                "Sorun devam ederse soruyu farklı bir ifadeyle yeniden deneyebilirsiniz."
            ),
            kaynaklar=[],       # Alakasız chunk referansları gösterilmez
            bulunamadi=True,    # DerleGecmis() bu turu geçmişe katmayacak
            fallback_kullanildi=True,
            islem_suresi_ms=islem_suresi_ms,
        )
