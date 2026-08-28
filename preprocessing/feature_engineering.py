"""
Feature Engineering
===================
Ham hasta verilerinden model özelliklerine dönüşüm.

Ham değer → Doğrudan özellik + Türetilmiş özellik

Yeni parametre geldiğinde:
  1. PatientFeatures schema'sına ekle
  2. Bu dosyada engineer_features() fonksiyonuna ekle
  3. Türetilmiş özellikler varsa klinisyen onayı al
"""

from __future__ import annotations

import numpy as np
from typing import Optional

from feature_store.schema import PatientFeatures, PsoriasisType
from config.settings import thresholds


# ─── Özellik Listesi ──────────────────────────────────────────────────────────
# Bu liste modelin beklediği sütun sıralamasını tanımlar.
# DEĞİŞTİRMEYİN — model artifact'ları bu listeye göre kaydedilir.
# Yeni özellikler SADECE listenin sonuna eklenir.

V1_FEATURES = [
    # Doğrudan özellikler
    "tirnak_tutulumu",
    "sabah_turuklugu",
    "vki",
    "ldl",
    "pasi_skoru",
    "sigara",
    # Türetilmiş — VKİ
    "vki_obez",
    "vki_asiri_obez",
    # Türetilmiş — LDL
    "ldl_yuksek",
    "ldl_cok_yuksek",
    # Türetilmiş — PASI
    "pasi_orta",
    "pasi_siddetli",
]

V2_FEATURES = [
    # v2.0 — Klinisyen parametreleri (opsiyonel, NaN toleranslı)
    "dlqi",
    "dlqi_yuksek",
    "bsa",
    "bsa_genis",
    "yas",
    "genc_hasta",
    # Psoriazis tipi — one-hot
    "tip_plak",
    "tip_gutat",
    "tip_inverz",
    "tip_pustular",
    "tip_eritrodermik",
    "tip_unknown",
    # Eklem
    "eklem_bulgulari",
    # Sistemik yanıt
    "onceki_iyi",
    "onceki_kotu",
    "onceki_yok",
]


def engineer_features(
    patient: PatientFeatures,
    include_v2: bool = False,
) -> dict[str, float]:
    """
    PatientFeatures → model özellik vektörü.

    Args:
        patient: Ham hasta özellikleri.
        include_v2: True ise v2.0 opsiyonel özellikleri de ekle.
                    Model v2.0 ile eğitilmişse True olmalı.

    Returns:
        Özellik adı → değer sözlüğü (float/int).
        Eksik v2.0 değerleri NaN olarak bırakılır (XGBoost bunu işler).
    """
    features: dict[str, float] = {}

    # ── v1.0: Doğrudan özellikler ─────────────────────────────────────────────
    features["tirnak_tutulumu"] = float(patient.tirnak_tutulumu)
    features["sabah_turuklugu"] = float(patient.sabah_turuklugu_30dk)
    features["vki"] = float(patient.vki)
    features["ldl"] = float(patient.ldl)
    features["pasi_skoru"] = float(patient.pasi_skoru)
    features["sigara"] = float(patient.sigara)

    # ── v1.0: Türetilmiş — VKİ ────────────────────────────────────────────────
    features["vki_obez"] = float(patient.vki > thresholds.VKI_OBEZ)
    features["vki_asiri_obez"] = float(patient.vki > thresholds.VKI_ASIRI_OBEZ)

    # ── v1.0: Türetilmiş — LDL ────────────────────────────────────────────────
    features["ldl_yuksek"] = float(patient.ldl > thresholds.LDL_YUKSEK)
    features["ldl_cok_yuksek"] = float(patient.ldl > thresholds.LDL_COK_YUKSEK)

    # ── v1.0: Türetilmiş — PASI ───────────────────────────────────────────────
    features["pasi_orta"] = float(
        thresholds.PASI_HAFIF_UST < patient.pasi_skoru <= thresholds.PASI_ORTA_UST
    )
    features["pasi_siddetli"] = float(patient.pasi_skoru > thresholds.PASI_ORTA_UST)

    # ── v1.0: Bileşik Risk Skoru ──────────────────────────────────────────────
    # Kardiyovasküler risk proxy (0–3 arası puanlama)
    features["kardiyovaskuler_risk"] = (
        features["vki_obez"]
        + features["ldl_yuksek"]
        + features["sigara"]
    )

    # Eklem tutulumu composite (tırnak veya sabah tutukluğu)
    features["eklem_risk"] = float(
        patient.tirnak_tutulumu or patient.sabah_turuklugu_30dk
    )

    # ── v1.0: Kural Motoru Özellikleri ────────────────────────────────────────
    # Mevcut if/else kurallarını feature olarak ekle → modelin kural mantığını
    # öğrenmesini ve üzerine koymasını sağlar.
    features["rule_ftr"] = float(
        patient.tirnak_tutulumu or patient.sabah_turuklugu_30dk
    )
    features["rule_aile"] = float(
        patient.vki > thresholds.VKI_OBEZ
        or patient.ldl > thresholds.LDL_YUKSEK
        or patient.sigara
    )
    features["rule_sistemik"] = float(patient.pasi_skoru > thresholds.PASI_ORTA_UST)

    # ── v2.0: Opsiyonel Klinik Parametreler ───────────────────────────────────
    if include_v2:
        # DLQI
        features["dlqi"] = float(patient.dlqi) if patient.dlqi is not None else np.nan
        features["dlqi_yuksek"] = (
            float(patient.dlqi > thresholds.DLQI_YUKSEK)
            if patient.dlqi is not None
            else np.nan
        )

        # BSA
        features["bsa"] = float(patient.bsa) if patient.bsa is not None else np.nan
        features["bsa_genis"] = (
            float(patient.bsa > thresholds.BSA_GENIS)
            if patient.bsa is not None
            else np.nan
        )

        # Yaş
        features["yas"] = float(patient.yas) if patient.yas is not None else np.nan
        features["genc_hasta"] = (
            float(patient.yas < thresholds.GENC_HASTA) if patient.yas is not None else np.nan
        )

        # Psoriazis tipi — one-hot encoding
        for tip in PsoriasisType:
            features[f"tip_{tip.value}"] = (
                float(patient.psoriazis_tipi == tip)
                if patient.psoriazis_tipi is not None
                else np.nan
            )

        # Eklem bulguları
        features["eklem_bulgulari"] = (
            float(patient.eklem_bulgulari)
            if patient.eklem_bulgulari is not None
            else np.nan
        )

        # Önceki sistemik yanıt
        if patient.onceki_sistemik_yanit is not None:
            features["onceki_iyi"] = float(patient.onceki_sistemik_yanit.value == "iyi")
            features["onceki_kotu"] = float(patient.onceki_sistemik_yanit.value == "kotu")
            features["onceki_yok"] = float(patient.onceki_sistemik_yanit.value == "yok")
        else:
            features["onceki_iyi"] = np.nan
            features["onceki_kotu"] = np.nan
            features["onceki_yok"] = np.nan

    # ── Extra features (geleceğe açık) ────────────────────────────────────────
    for key, value in patient.extra_features.items():
        features[f"extra_{key}"] = float(value)

    return features


def get_feature_names(include_v2: bool = False) -> list[str]:
    """
    Modelin beklediği özellik sütun adlarını döner.
    Model kaydedilirken bu liste de kaydedilmeli.
    """
    names = V1_FEATURES.copy()
    if include_v2:
        names.extend(V2_FEATURES)
    return names
