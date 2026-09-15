"""
Klinik Kılavuz Bilgi Tabanı (Guidelines Knowledge Base)
=========================================================
Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD) ve
EuroGuiDerm 2025 kılavuzlarından distile edilmiş, yapısal klinik bilgi.

Tasarım Kararı:
    Runtime'da PDF parse etmek yerine, kılavuzların SEDA kararlarıyla
    doğrudan ilgili kısımları Python nesnelerine dönüştürüldü.
    Bu yaklaşım:
    - Her predict çağrısında ~0ms ek süre (bellekte, dosya I/O yok)
    - LLM'in atıf uydurma riskini sıfıra indirir (atıflar koddan gelir)
    - Kılavuz güncellemelerinde sadece bu dosya güncellenir

Kaynak Belgeler:
    [TR2025] Türkiye Psoriasis Tedavi Kılavuzu 2025
             Türk Dermatoloji Derneği — Psoriasis Çalışma Grubu (PSOKİD)
             www.psokid.org

    [EG2025] EuroGuiDerm Guideline for the Systemic Treatment of Psoriasis Vulgaris
             European Dermatology Forum (EDF) — Eylül 2023, Güncelleme Şubat 2025
             DOI: 10.1111/jdv.16752
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ─── Veri Yapıları ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ClinicalCitation:
    """Tek bir kılavuz atıfını temsil eder."""

    kaynak_kodu: str
    """'TR2025' veya 'EG2025'"""

    kaynak_adi: str
    """İnsan okunabilir kısa kaynak adı."""

    bolum: str
    """Bölüm/chapter başlığı."""

    sayfa: str
    """Sayfa numarası veya aralığı (örn: '11' veya '23-24')."""

    icerik: str
    """Kılavuzdan alınan öze sadık özet (orijinal dil korunur)."""

    karar_turu: str
    """Bu atıfın hangi klinik karar türüyle ilişkili olduğu:
    'ftr' | 'sistemik_tedavi' | 'aile_hekimligi' | 'genel'"""

    tetikleyici_kosul: str
    """Bu atıfın hangi koşulda aktive olduğu — serbest metin açıklaması."""

    def format_for_prompt(self) -> str:
        """LLM prompt'una eklenecek formatlı atıf metni."""
        return (
            f"[{self.kaynak_kodu}, s.{self.sayfa}] {self.bolum}: "
            f"{self.icerik}"
        )

    def format_for_pdf(self) -> str:
        """PDF raporuna eklenecek tam bibliyografik format."""
        return (
            f"{self.kaynak_adi}. "
            f"{self.bolum}. "
            f"Sayfa {self.sayfa}."
        )


# ─── Kılavuz Bilgi Tabanı ─────────────────────────────────────────────────────

class GuidelinesKnowledgeBase:
    """
    2025 Psoriasis kılavuzlarından distile edilmiş klinik bilgi tabanı.

    SEDA'nın üç karar türüne (FTR, Sistemik Tedavi, Aile Hekimliği) göre
    yapılandırılmış, her karar için ilgili kılavuz maddelerini, eşik
    değerlerini ve özel durumları içerir.
    """

    def __init__(self) -> None:
        self._atiflar: list[ClinicalCitation] = self._build_citation_library()

    # ─── Atıf Kütüphanesi ─────────────────────────────────────────────────────

    def _build_citation_library(self) -> list[ClinicalCitation]:
        """
        Kılavuzlardan elle distile edilmiş atıf kütüphanesini oluşturur.
        Kılavuz güncellemesinde sadece bu metod güncellenir.
        """
        atiflar: list[ClinicalCitation] = []

        # ── FTR / Romatoloji Sevki Atıfları ──────────────────────────────────

        atiflar.append(ClinicalCitation(
            kaynak_kodu="TR2025",
            kaynak_adi="Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD)",
            bolum="Hastalık Şiddetinin Tanımlanması — Özel Durum Endikasyonları",
            sayfa="11",
            icerik=(
                "Tırnak psoriazisi psoriatik artritin klinik habercisi olarak "
                "kabul edilmekte; en az iki tırnakta onikoliz veya onikodistrofi "
                "varlığı, PASI skoru bağımsız olarak hastalığı orta-şiddetli "
                "kategorisine taşımakta ve eklem tutulumu açısından erken "
                "değerlendirmeyi zorunlu kılmaktadır."
            ),
            karar_turu="ftr",
            tetikleyici_kosul="tirnak_tutulumu=True",
        ))

        atiflar.append(ClinicalCitation(
            kaynak_kodu="EG2025",
            kaynak_adi="EuroGuiDerm Guideline — Systemic Treatment of Psoriasis Vulgaris (2025)",
            bolum="Table 3: Psoriatic Arthritis — Comorbidity Management",
            sayfa="19",
            icerik=(
                "Psoriatik artrit şüphesi taşıyan hastalarda (eklem şişliği, "
                "entezit, daktilit veya sabah tutukluğu > 30 dakika) dermatolog "
                "ve romatolog iş birliği ile ortak yönetim planlanması "
                "önerilmektedir. Anti-TNF, Anti-IL17 ve Anti-IL23 biyolojikler "
                "hem deri hem eklem komponentini hedef alabilmektedir."
            ),
            karar_turu="ftr",
            tetikleyici_kosul="sabah_turuklugu_30dk=True veya eklem_bulgulari=True",
        ))

        atiflar.append(ClinicalCitation(
            kaynak_kodu="EG2025",
            kaynak_adi="EuroGuiDerm Guideline — Systemic Treatment of Psoriasis Vulgaris (2025)",
            bolum="Bölüm VIII: Decision Grid II — Psoriatic Arthritis Comorbidity",
            sayfa="5-7",
            icerik=(
                "Eklem tutulumu eşlik eden psoriazis vakalarında dermatologun "
                "yönetim planına romatoloji konsültasyonunun dahil edilmesi, "
                "uzun vadeli eklem hasarını azaltmada kritik öneme sahiptir."
            ),
            karar_turu="ftr",
            tetikleyici_kosul="eklem_bulgulari=True",
        ))

        # ── Sistemik Tedavi Atıfları ──────────────────────────────────────────

        atiflar.append(ClinicalCitation(
            kaynak_kodu="TR2025",
            kaynak_adi="Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD)",
            bolum="Hastalık Şiddetinin Tanımlanması — Orta-Şiddetli Plak Psoriazisi",
            sayfa="11",
            icerik=(
                "PASI > 10 veya BSA > %10 değerleri sistemik tedavi endikasyonu "
                "için temel eşik değerleri olarak benimsenmiştir. Topikal tedaviye "
                "dirençli, intoleran veya topikal tedavinin kontrendike olduğu "
                "hastalarda konvansiyonel sistemik tedaviye (metotreksat, asitretin, "
                "siklosporin) geçiş önerilmektedir."
            ),
            karar_turu="sistemik_tedavi",
            tetikleyici_kosul="pasi_skoru > 10 veya bsa > 10",
        ))

        atiflar.append(ClinicalCitation(
            kaynak_kodu="TR2025",
            kaynak_adi="Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD)",
            bolum="Hastalık Şiddetinin Tanımlanması — DLQI Eşiği",
            sayfa="4-5",
            icerik=(
                "DLQI > 10, hastanın yaşam kalitesinin ciddi ölçüde etkilendiğini "
                "göstermekte ve PASI/BSA değerinden bağımsız olarak sistemik "
                "tedavi değerlendirmesine zemin hazırlamaktadır. Psoriasisli "
                "hastalarda yaşam kalitesinin kanser ve diyabet kadar etkilenebildiği "
                "bilinmektedir."
            ),
            karar_turu="sistemik_tedavi",
            tetikleyici_kosul="dlqi > 10",
        ))

        atiflar.append(ClinicalCitation(
            kaynak_kodu="EG2025",
            kaynak_adi="EuroGuiDerm Guideline — Systemic Treatment of Psoriasis Vulgaris (2025)",
            bolum="Bölüm VII: Disease Severity and Treatment Goals",
            sayfa="23-24",
            icerik=(
                "EuroGuiDerm 2025 kılavuzu psoriazisi ikiye indirger: topikal tedavi "
                "adayları ve sistemik tedavi adayları. Sistemik tedaviye aday olma "
                "kriterleri: (1) BSA > %10, (2) özel lokalizasyon tutulumu "
                "(avuç içi, ayak tabanı, yüz, genital), (3) DLQI > 10. "
                "Tedavi hedefi: PASI75 (PASI bazal değerden %75 azalma) veya "
                "mutlak PASI ≤ 3."
            ),
            karar_turu="sistemik_tedavi",
            tetikleyici_kosul="pasi_skoru > 10 veya dlqi > 10 veya bsa > 10",
        ))

        atiflar.append(ClinicalCitation(
            kaynak_kodu="TR2025",
            kaynak_adi="Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD)",
            bolum="Tedavi Basamaklandırması — Biyolojik Ajanlara Geçiş",
            sayfa="42-43",
            icerik=(
                "Konvansiyonel sistemik tedaviye yetersiz yanıt, intolerans veya "
                "kontrendikasyon varlığında biyolojik ajan veya küçük molekül "
                "(JAK/TYK2 inhibitörü) tedavisine geçiş kriterleri: "
                "PASI75 yanıtının sağlanamaması ya da DLQI'nin yeterince "
                "düşmemesi. Aktif tüberküloz taraması (Tüberkülin testi, IGRA) "
                "ve hepatit serolojisi biyolojik ajan başlanmadan önce zorunludur."
            ),
            karar_turu="sistemik_tedavi",
            tetikleyici_kosul="pasi_skoru > 20 (şiddetli)",
        ))

        # ── Aile Hekimliği Atıfları ───────────────────────────────────────────

        atiflar.append(ClinicalCitation(
            kaynak_kodu="TR2025",
            kaynak_adi="Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD)",
            bolum="Giriş — Komorbidite ve Sistemik İnflamasyon",
            sayfa="2",
            icerik=(
                "Psoriazis; metabolik sendrom, kardiyovasküler hastalık, "
                "psikiyatrik bozukluklar ve insülin direnciyle birlikte seyretmektedir. "
                "Altta yatan kronik inflamatuvar sürecin birden fazla organ sistemini "
                "etkilediği bilinmekte, kardiyovasküler risk takibinin poliklinik "
                "sürecine entegrasyonu önerilmektedir."
            ),
            karar_turu="aile_hekimligi",
            tetikleyici_kosul="vki > 30 veya ldl > 130 veya sigara=True",
        ))

        atiflar.append(ClinicalCitation(
            kaynak_kodu="EG2025",
            kaynak_adi="EuroGuiDerm Guideline — Systemic Treatment of Psoriasis Vulgaris (2025)",
            bolum="Table 3: Cardiovascular Comorbidity — Diabetes mellitus & Heart disease",
            sayfa="19",
            icerik=(
                "Psoriazis hastalarında obezite (VKİ ≥ 30) ve dislipidemi "
                "(LDL ≥ 130 mg/dL) varlığı majör kardiyovasküler olaylar için "
                "bağımsız risk faktörü oluşturmaktadır. Bu hastalarda birinci "
                "basamak sağlık düzeyinde düzenli kardiyometabolik izlem "
                "(kan lipid profili, kan şekeri, kan basıncı) planlanması "
                "önerilmektedir."
            ),
            karar_turu="aile_hekimligi",
            tetikleyici_kosul="vki > 30 veya ldl > 130",
        ))

        atiflar.append(ClinicalCitation(
            kaynak_kodu="EG2025",
            kaynak_adi="EuroGuiDerm Guideline — Systemic Treatment of Psoriasis Vulgaris (2025)",
            bolum="Bölüm III: Special Considerations — Smoking and Cardiovascular Risk",
            sayfa="3",
            icerik=(
                "Aktif sigara kullanımı psoriazis şiddetini artırmakta, "
                "tedaviye yanıtı olumsuz etkilemekte ve kardiyovasküler "
                "risk profilini kötüleştirmektedir. Sigara bırakma danışmanlığı "
                "ve kardiyovasküler risk yönetimi için birinci basamağa "
                "yönlendirme, psoriazis yönetiminin ayrılmaz parçasıdır."
            ),
            karar_turu="aile_hekimligi",
            tetikleyici_kosul="sigara=True",
        ))

        # ── Genel / Ortak Atıflar ─────────────────────────────────────────────

        atiflar.append(ClinicalCitation(
            kaynak_kodu="TR2025",
            kaynak_adi="Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD)",
            bolum="Hastalık Şiddetinin Tanımlanması — PASI Ölçeği",
            sayfa="4",
            icerik=(
                "PASI (Psoriasis Alan Şiddet İndeksi), plak tipi psoriazisde "
                "hastalık şiddetinin değerlendirilmesinde güvenilir ve "
                "tekrarlanabilir bir ölçektir. Eşik değerleri: "
                "PASI ≤ 5 hafif, 5-10 orta, > 10 şiddetli psoriazis."
            ),
            karar_turu="genel",
            tetikleyici_kosul="her zaman",
        ))

        atiflar.append(ClinicalCitation(
            kaynak_kodu="EG2025",
            kaynak_adi="EuroGuiDerm Guideline — Systemic Treatment of Psoriasis Vulgaris (2025)",
            bolum="Bölüm VII: Treatment Goals",
            sayfa="25",
            icerik=(
                "Tedavi hedefi olarak 'minimum hastalık aktivitesi' tanımı "
                "benimsenmiştir: Tedaviden 16-24 hafta sonra PASI ≤ 3 veya "
                "PASI75 yanıtı ve DLQI ≤ 5. Bu hedefe ulaşılamayan hastalarda "
                "tedavi modifikasyonu veya biyolojik ajana geçiş değerlendirilmelidir."
            ),
            karar_turu="genel",
            tetikleyici_kosul="her zaman",
        ))

        return atiflar

    # ─── Karar Mantığı ────────────────────────────────────────────────────────

    def get_relevant_citations(
        self,
        ftr_karari: bool,
        sistemik_karari: bool,
        aile_hek_karari: bool,
        pasi: Optional[float] = None,
        bsa: Optional[float] = None,
        dlqi: Optional[float] = None,
        vki: Optional[float] = None,
        ldl: Optional[float] = None,
        tirnak_tutulumu: bool = False,
        sabah_turuklugu: bool = False,
        eklem_bulgulari: Optional[bool] = None,
        sigara: bool = False,
    ) -> list[ClinicalCitation]:
        """
        Aktif kararlara ve hasta parametrelerine göre ilgili atıfları seçer.

        Args:
            Klinik karar booleanları ve hasta parametreleri.

        Returns:
            Sıralanmış ve tekilleştirilmiş ClinicalCitation listesi.
        """
        secilen: list[ClinicalCitation] = []

        # Genel atıfları her zaman dahil et
        genel_atiflar = [a for a in self._atiflar if a.karar_turu == "genel"]
        secilen.extend(genel_atiflar)

        # FTR kararı aktifse ilgili atıfları seç
        if ftr_karari:
            if tirnak_tutulumu:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "ftr" and "tirnak" in a.tetikleyici_kosul
                )
            if sabah_turuklugu:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "ftr" and "sabah" in a.tetikleyici_kosul
                )
            if eklem_bulgulari:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "ftr" and "eklem" in a.tetikleyici_kosul
                )
            # Hiçbiri eşleşmediyse tüm FTR atıflarını al
            ftr_eklendi = any(a.karar_turu == "ftr" for a in secilen)
            if not ftr_eklendi:
                secilen.extend(a for a in self._atiflar if a.karar_turu == "ftr")

        # Sistemik tedavi kararı aktifse ilgili atıfları seç
        if sistemik_karari:
            if pasi is not None and pasi > 10:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "sistemik_tedavi" and "pasi" in a.tetikleyici_kosul.lower()
                )
            if dlqi is not None and dlqi > 10:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "sistemik_tedavi" and "dlqi" in a.tetikleyici_kosul.lower()
                )
            if pasi is not None and pasi > 20:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "sistemik_tedavi" and "> 20" in a.tetikleyici_kosul
                )
            # Hiçbiri eşleşmediyse birincil sistemik atıfları al
            sistemik_eklendi = any(a.karar_turu == "sistemik_tedavi" for a in secilen)
            if not sistemik_eklendi:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "sistemik_tedavi" and "pasi" in a.tetikleyici_kosul.lower()
                )

        # Aile Hekimliği kararı aktifse ilgili atıfları seç
        if aile_hek_karari:
            if vki is not None and vki > 30:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "aile_hekimligi" and "vki" in a.tetikleyici_kosul.lower()
                )
            if ldl is not None and ldl > 130:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "aile_hekimligi" and "ldl" in a.tetikleyici_kosul.lower()
                )
            if sigara:
                secilen.extend(
                    a for a in self._atiflar
                    if a.karar_turu == "aile_hekimligi" and "sigara" in a.tetikleyici_kosul.lower()
                )
            # Hiçbiri eşleşmediyse genel AH atıfını al
            ah_eklendi = any(a.karar_turu == "aile_hekimligi" for a in secilen)
            if not ah_eklendi:
                secilen.extend(
                    a for a in self._atiflar if a.karar_turu == "aile_hekimligi"
                )

        # Tekrarları kaldır — sıra koruyarak
        goruldu: set[str] = set()
        tekillestirilmis: list[ClinicalCitation] = []
        for atif in secilen:
            anahtar = f"{atif.kaynak_kodu}-{atif.sayfa}"
            if anahtar not in goruldu:
                goruldu.add(anahtar)
                tekillestirilmis.append(atif)

        return tekillestirilmis

    # ─── Format Yardımcıları ──────────────────────────────────────────────────

    def format_for_prompt(self, citations: list[ClinicalCitation]) -> str:
        """
        LLM prompt'una eklenecek yapılandırılmış klinik dayanak bloğunu üretir.
        """
        if not citations:
            return ""

        lines = [
            "KLİNİK DAYANAK — RESMİ KILAVUZ ATIFLAR:",
            "Bu kararlar aşağıdaki güncel kılavuzlarla uyumludur. "
            "Epikrizde bu dayanakları doğal klinik dille kullan; "
            "kılavuz adını parantez içinde belirtebilirsin:",
            "",
        ]
        for i, atif in enumerate(citations, 1):
            lines.append(f"[{i}] {atif.format_for_prompt()}")

        lines.append(
            "\nYönlendirme: Uygun yerlerde 'Türkiye Psoriasis Kılavuzu 2025 uyarınca...' "
            "veya 'EuroGuiDerm 2025 kriterleri çerçevesinde...' gibi "
            "doğal klinik ifadeler kullan."
        )

        return "\n".join(lines)

    def format_for_pdf(self, citations: list[ClinicalCitation]) -> list[str]:
        """
        PDF raporuna eklenecek bibliyografik referans listesini döndürür.
        Her öğe bağımsız bir referans satırıdır.
        """
        if not citations:
            return []

        # Kaynak koduna göre grupla — her kaynağı bir kez biblio olarak göster
        gorulenler: set[str] = set()
        referanslar: list[str] = []

        for atif in citations:
            if atif.kaynak_kodu not in gorulenler:
                gorulenler.add(atif.kaynak_kodu)
                if atif.kaynak_kodu == "TR2025":
                    referanslar.append(
                        "Türk Dermatoloji Derneği Psoriasis Çalışma Grubu (PSOKİD). "
                        "Türkiye Psoriasis Tedavi Kılavuzu 2025. "
                        "www.psokid.org, Ekim 2025."
                    )
                elif atif.kaynak_kodu == "EG2025":
                    referanslar.append(
                        "Nast A, Spuls PI, et al. EuroGuiDerm Guideline for the Systemic "
                        "Treatment of Psoriasis Vulgaris. "
                        "European Dermatology Forum (EDF), Eylül 2023 — Güncelleme Şubat 2025. "
                        "DOI: 10.1111/jdv.16752."
                    )

        return referanslar

    def format_citations_for_api(self, citations: list[ClinicalCitation]) -> list[str]:
        """
        API yanıtına eklenecek kısa atıf listesini döndürür.
        Frontend'e her atıf için kısa, okunabilir bir string gönderir.
        """
        return [
            f"{a.kaynak_kodu} — {a.bolum} (s.{a.sayfa})"
            for a in citations
        ]


# ─── Singleton ────────────────────────────────────────────────────────────────

guidelines_kb = GuidelinesKnowledgeBase()
