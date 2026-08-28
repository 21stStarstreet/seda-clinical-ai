"""
Sentetik Veri Üreteci
=====================
Kural tabanlı mevcut sistemi ground truth olarak kullanarak
gerçekçi sentetik hasta verileri üretir.

Amaç:
  - Gerçek hasta verisi gelene kadar pipeline'ı test etmek
  - Modelin kural mantığını öğrenmesi için temel veri sağlamak

UYARI:
  - Bu veri SADECE geliştirme ve pipeline testi için kullanılır.
  - Klinik karar veya validasyon için kullanılmaz.
  - Gerçek veri geldiğinde bu script devre dışı kalır.

Kullanım:
    python scripts/generate_synthetic_data.py --n 1000 --output data/synthetic/patients.parquet
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import set_global_seed, thresholds, LABEL_NAMES
from feature_store.schema import PatientFeatures, PatientLabels


def apply_rule_engine(patient: PatientFeatures) -> PatientLabels:
    """
    Mevcut if/else kural motoru.
    Sentetik veri için ground truth üretir.
    Bu fonksiyon, gerçek sistemdeki kural motorunun birebir kopyasıdır.
    """
    ftr = patient.tirnak_tutulumu or patient.sabah_turuklugu_30dk

    # Aile hekimligi: Age factor added
    aile_hekimligi = (
        patient.vki > thresholds.VKI_OBEZ
        or patient.ldl > thresholds.LDL_YUKSEK
        or patient.sigara
        or (patient.yas is not None and patient.yas > 50 and (patient.vki > 25 or patient.ldl > 130))
    )

    # Sistemik tedavi: Rule of Tens (PASI > 10 OR BSA > 10 OR DLQI > 10)
    sistemik_tedavi = (
        patient.pasi_skoru > thresholds.PASI_ORTA_UST
        or (patient.dlqi is not None and patient.dlqi > 10)
        or (patient.bsa is not None and patient.bsa > 10)
    )

    return PatientLabels(
        ftr=bool(ftr),
        aile_hekimligi=bool(aile_hekimligi),
        sistemik_tedavi=bool(sistemik_tedavi),
    )


def generate_patient(rng: np.random.Generator) -> PatientFeatures:
    """
    Klinik olarak gerçekçi tek bir sentetik hasta üret.

    Dağılımlar Türk psoriazis popülasyonunu yaklaşık temsil eder
    (klinisyen onayıyla kalibre edilebilir).
    """
    # Tırnak tutulumu: Psoriazis hastalarında ~%40 görülür
    tirnak = rng.random() < 0.40

    # Sabah tutukluğu: Artropati riski olan ~%30
    sabah = rng.random() < 0.30

    # VKİ: Türk yetişkin ortalaması ~27, psoriazis hastalarında hafif yüksek
    # Truncated normal benzeri: minimum 15, maksimum 55
    vki = float(np.clip(rng.normal(loc=28.5, scale=6.0), 15.0, 55.0))

    # LDL: Normal dağılım, mg/dL
    ldl = float(np.clip(rng.normal(loc=118.0, scale=32.0), 40.0, 280.0))

    # PASI: Sağa çarpık (hafif vakalar çoğunlukta)
    # Exponential dağılım, ama üstten kesilmiş
    pasi = float(np.clip(rng.exponential(scale=7.5), 0.0, 72.0))

    # Sigara: Türk yetişkin erkek ~%45, kadın ~%20 (genel: ~%35)
    sigara = rng.random() < 0.35

    # Yaş: Yetişkin hasta popülasyonu (18-80)
    yas = int(np.clip(rng.normal(loc=45, scale=15), 18, 80))

    # BSA: Genellikle PASI ile orantılıdır
    bsa = float(np.clip(pasi * 1.1 + rng.normal(loc=0, scale=3), 0.0, 100.0))

    # DLQI: Yaşam kalitesi, PASI ve semptomlara bağlıdır
    dlqi_base = pasi * 0.5 + (5 if tirnak else 0) + (5 if sabah else 0)
    dlqi = float(np.clip(dlqi_base + rng.normal(loc=0, scale=3), 0.0, 30.0))

    return PatientFeatures(
        tirnak_tutulumu=bool(tirnak),
        sabah_turuklugu_30dk=bool(sabah),
        vki=round(vki, 1),
        ldl=round(ldl, 1),
        pasi_skoru=round(pasi, 1),
        sigara=bool(sigara),
        yas=yas,
        bsa=round(bsa, 1),
        dlqi=round(dlqi, 1),
    )


def generate_dataset(
    n: int = 1000,
    seed: int = 42,
    noise_rate: float = 0.02,
) -> tuple[list[PatientFeatures], list[PatientLabels]]:
    """
    n adet sentetik hasta ve etiket üret.

    Args:
        n: Üretilecek hasta sayısı.
        seed: Tekrar üretilebilirlik için.
        noise_rate: Kural motorundan sapma oranı (gerçek dünya gürültüsü için).
                    0.0 = tamamen deterministik kural çıktısı.
                    0.02 = %2 rastgele etiket flip'i (gerçekçilik için).

    Returns:
        (patients, labels) tuple'ı.
    """
    set_global_seed(seed)
    rng = np.random.default_rng(seed)

    patients: list[PatientFeatures] = []
    labels: list[PatientLabels] = []

    for i in range(n):
        patient = generate_patient(rng)
        patient.hasta_id = f"SYN-{i + 1:05d}"
        patient.kayit_tarihi = "2024-01-01"

        label = apply_rule_engine(patient)

        # Gürültü ekle (gerçek hasta verisini simüle etmek için)
        if noise_rate > 0:
            label = _add_noise(label, rng, noise_rate)

        patients.append(patient)
        labels.append(label)

    return patients, labels


def _add_noise(
    label: PatientLabels,
    rng: np.random.Generator,
    rate: float,
) -> PatientLabels:
    """
    Etiketlere küçük miktarda rastgele gürültü ekle.
    Bu, gerçek hasta verilerindeki klinisyen yargı farklılıklarını simüle eder.
    """
    arr = label.to_array()
    for i in range(len(arr)):
        if rng.random() < rate:
            arr[i] = 1 - arr[i]  # Flip
    return PatientLabels.from_array(arr)


def to_dataframe(
    patients: list[PatientFeatures],
    labels: list[PatientLabels],
) -> pd.DataFrame:
    """Hasta listesini analiz için pandas DataFrame'e çevir."""
    rows = []
    for patient, label in zip(patients, labels):
        row = {
            "hasta_id": patient.hasta_id,
            # Özellikler
            "tirnak_tutulumu": int(patient.tirnak_tutulumu),
            "sabah_turuklugu_30dk": int(patient.sabah_turuklugu_30dk),
            "vki": patient.vki,
            "ldl": patient.ldl,
            "pasi_skoru": patient.pasi_skoru,
            "sigara": int(patient.sigara),
            # Etiketler
            "label_ftr": int(label.ftr),
            "label_aile_hekimligi": int(label.aile_hekimligi),
            "label_sistemik_tedavi": int(label.sistemik_tedavi),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def print_dataset_summary(df: pd.DataFrame) -> None:
    """Veri seti istatistiklerini yazdır."""
    print("\n" + "=" * 60)
    print("SENTETİK VERİ SETİ ÖZETİ")
    print("=" * 60)
    print(f"Toplam hasta sayısı: {len(df)}")
    print()
    print("Sayısal özellik istatistikleri:")
    print(df[["vki", "ldl", "pasi_skoru"]].describe().round(2).to_string())
    print()
    print("Binary özellik dağılımı:")
    for col in ["tirnak_tutulumu", "sabah_turuklugu_30dk", "sigara"]:
        rate = df[col].mean() * 100
        print(f"  {col}: %{rate:.1f} pozitif")
    print()
    print("Label dağılımı:")
    for col in ["label_ftr", "label_aile_hekimligi", "label_sistemik_tedavi"]:
        rate = df[col].mean() * 100
        print(f"  {col}: %{rate:.1f} pozitif")
    print()
    # Multi-label kombinasyonları
    combo = df[["label_ftr", "label_aile_hekimligi", "label_sistemik_tedavi"]].apply(
        lambda r: f"FTR={r[0]} AH={r[1]} SİS={r[2]}", axis=1
    )
    print("En yaygın kombinasyonlar:")
    print(combo.value_counts().head(8).to_string())
    print("=" * 60)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Psoriazis CDSS için sentetik hasta verisi üret."
    )
    parser.add_argument(
        "--n", type=int, default=1000,
        help="Üretilecek hasta sayısı (default: 1000)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--noise", type=float, default=0.02,
        help="Gürültü oranı 0.0–0.1 (default: 0.02)"
    )
    parser.add_argument(
        "--output", type=str, default="data/synthetic/patients.parquet",
        help="Çıktı dosya yolu (.parquet veya .csv)"
    )
    args = parser.parse_args()

    print(f"[Sentetik Veri] {args.n} hasta üretiliyor (seed={args.seed}, noise={args.noise})...")

    patients, labels = generate_dataset(n=args.n, seed=args.seed, noise_rate=args.noise)
    df = to_dataframe(patients, labels)

    print_dataset_summary(df)

    # Kaydet
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if str(output_path).endswith(".parquet"):
        df.to_parquet(output_path, index=False)
    else:
        df.to_csv(output_path, index=False, encoding="utf-8")

    print(f"\n[Sentetik Veri] Kaydedildi: {output_path}")
    print(f"[Sentetik Veri] Boyut: {df.shape}")


if __name__ == "__main__":
    main()
