"""
Feature Store Şeması
====================
Hasta özelliklerini tanımlayan merkezi veri modeli.

v1.0 — 6 temel parametre (kural motoru parametreleri)
v2.0 — Ek klinik parametreler (hoca onayını bekliyor)

Yeni parametre eklemek için:
  1. Bu dosyada Optional alan olarak tanımla
  2. preprocessing/feature_engineering.py'yi güncelle
  3. schema_version'ı artır
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─── Kategorik Tipler ─────────────────────────────────────────────────────────

class PsoriasisType(str, Enum):
    """Psoriazis klinik alt tipleri."""
    PLAK = "plak"
    GUTAT = "gutat"
    INVERZ = "inverz"
    PUSTULAR = "pustular"
    ERITRODERMIK = "eritrodermik"
    UNKNOWN = "unknown"


class Gender(str, Enum):
    ERKEK = "E"
    KADIN = "K"
    BELIRTILMEMIS = "B"


class SystemicResponse(str, Enum):
    """Önceki sistemik tedaviye yanıt."""
    IYI = "iyi"
    KOTU = "kotu"
    YOK = "yok"          # Daha önce sistemik tedavi almamış
    BILINMIYOR = "bilinmiyor"


# ─── Ana Veri Modeli ──────────────────────────────────────────────────────────

@dataclass
class PatientFeatures:
    """
    Psoriazis hasta özellikleri.

    Zorunlu alanlar (v1.0 — kural motoru parametreleri):
      tirnak_tutulumu, sabah_turuklugu_30dk, vki, ldl, pasi_skoru, sigara

    Opsiyonel alanlar (v2.0 — klinisyen parametreleri, henüz bekleniyor):
      dlqi, bsa, psoriazis_tipi, yas, cinsiyet, hastalik_suresi_ay,
      eklem_bulgulari, onceki_sistemik_yanit

    Kullanım:
        patient = PatientFeatures(
            tirnak_tutulumu=True,
            sabah_turuklugu_30dk=True,
            vki=33.2,
            ldl=145.0,
            pasi_skoru=7.2,
            sigara=True,
        )
    """

    # ── v1.0 — Zorunlu Parametreler ───────────────────────────────────────────
    tirnak_tutulumu: bool
    """Psoriazis artropatisi göstergesi. True = tırnak tutulumu var."""

    sabah_turuklugu_30dk: bool
    """30 dakikadan uzun sabah tutukluğu. True = var. FTR göstergesi."""

    vki: float
    """Vücut Kitle İndeksi (kg/m²). Eşik: >30 obez, >35 morbid obez."""

    ldl: float
    """LDL kolesterol (mg/dL). Eşik: >130 yüksek, >160 çok yüksek."""

    pasi_skoru: float
    """
    Psoriasis Area and Severity Index (0–72).
    <5: hafif, 5–10: orta, >10: şiddetli (sistemik tedavi endikasyonu).
    """

    sigara: bool
    """Aktif sigara kullanımı. True = kullanıyor."""

    # ── v2.0 — Opsiyonel Klinik Parametreler (Yakında Eklenecek) ─────────────

    dlqi: Optional[float] = None
    """
    Dermatology Life Quality Index (0–30).
    >10: hayat kalitesi ciddi ölçüde etkilenmiş.
    """

    bsa: Optional[float] = None
    """
    Body Surface Area — etkilenen vücut yüzey alanı (%).
    >10: yaygın tutulum.
    """

    psoriazis_tipi: Optional[PsoriasisType] = None
    """Psoriazis klinik alt tipi. Bkz: PsoriasisType enum."""

    yas: Optional[int] = None
    """Hasta yaşı (yıl)."""

    cinsiyet: Optional[Gender] = None
    """Hasta cinsiyeti. Bkz: Gender enum."""

    hastalik_suresi_ay: Optional[int] = None
    """Hastalık süresi (ay cinsinden)."""

    eklem_bulgulari: Optional[bool] = None
    """
    Psoriazis artropatisi eklem bulguları.
    True: şişlik, hassasiyet, krepitasyon vb. mevcut.
    """

    onceki_sistemik_yanit: Optional[SystemicResponse] = None
    """Önceki sistemik tedaviye yanıt durumu. Bkz: SystemicResponse enum."""

    # ── Gelecek Parametreler için Açık Alan ───────────────────────────────────

    extra_features: dict = field(default_factory=dict)
    """
    Şemada tanımlı olmayan ek özellikler için esnek alan.
    Yeni parametreler önce buraya girer, sonra schema'ya taşınır.
    Format: {'ozellik_adi': deger}
    """

    # ── Metadata ──────────────────────────────────────────────────────────────

    hasta_id: Optional[str] = None
    """Anonim hasta kimliği. Kişisel veri içermemelidir."""

    hasta_adi: Optional[str] = None
    """Hasta Adı Soyadı. Şifrelenmiş alanda (input_json) saklanacaktır."""

    kayit_tarihi: Optional[str] = None
    """ISO 8601 format: '2024-01-15T10:30:00'"""

    schema_version: str = "1.0"
    """
    Bu kaydın hangi schema versiyonuyla oluşturulduğunu belirtir.
    Model versiyonlamayla eşleştirilir.
    """

    def to_dict(self) -> dict:
        """Tüm alanları dict olarak döner (serializasyon için).
        Enum değerleri otomatik olarak string'e dönüştürülür (JSON uyumlu)."""
        from dataclasses import asdict

        def _serialize(obj):
            if isinstance(obj, Enum):
                return obj.value
            return obj

        raw = asdict(self)
        return {k: _serialize(v) for k, v in raw.items()}

    def validate(self) -> list[str]:
        """
        Temel klinik mantık doğrulaması.
        Sorun varsa uyarı mesajları listesi döner.
        """
        warnings = []

        if not (10 <= self.vki <= 80):
            warnings.append(f"VKİ değeri ({self.vki}) beklenen aralık dışında (10–80).")
        if not (0 <= self.ldl <= 500):
            warnings.append(f"LDL değeri ({self.ldl}) beklenen aralık dışında (0–500).")
        if not (0 <= self.pasi_skoru <= 72):
            warnings.append(f"PASI skoru ({self.pasi_skoru}) beklenen aralık dışında (0–72).")
        if self.dlqi is not None and not (0 <= self.dlqi <= 30):
            warnings.append(f"DLQI değeri ({self.dlqi}) beklenen aralık dışında (0–30).")
        if self.bsa is not None and not (0 <= self.bsa <= 100):
            warnings.append(f"BSA değeri ({self.bsa}) beklenen aralık dışında (0–100).")
        if self.yas is not None and not (0 <= self.yas <= 120):
            warnings.append(f"Yaş değeri ({self.yas}) beklenen aralık dışında (0–120).")
        if self.hastalik_suresi_ay is not None and not (0 <= self.hastalik_suresi_ay <= 1200):
            warnings.append(f"Hastalık süresi ({self.hastalik_suresi_ay} ay) beklenen aralık dışında (0–1200).")

        return warnings


# ─── Label Modeli ─────────────────────────────────────────────────────────────

@dataclass
class PatientLabels:
    """
    Bir hasta için gerçek veya tahmin edilen çıktı etiketleri.

    Multi-label: her alan bağımsız bir ikili karar.
    """
    ftr: bool
    """Fizik Tedavi ve Rehabilitasyon sevki."""

    aile_hekimligi: bool
    """Aile Hekimliği sevki."""

    sistemik_tedavi: bool
    """Sistemik Tedavi başlatma önerisi."""

    def to_array(self) -> list[int]:
        """[ftr, aile_hekimligi, sistemik_tedavi] olarak döner."""
        return [int(self.ftr), int(self.aile_hekimligi), int(self.sistemik_tedavi)]

    @classmethod
    def from_array(cls, arr: list[int]) -> "PatientLabels":
        """[0/1, 0/1, 0/1] dizisinden oluşturur."""
        return cls(
            ftr=bool(arr[0]),
            aile_hekimligi=bool(arr[1]),
            sistemik_tedavi=bool(arr[2]),
        )
