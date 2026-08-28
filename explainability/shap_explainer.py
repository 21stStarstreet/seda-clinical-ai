"""
SHAP Explainability
===================
Her label için TreeExplainer kullanarak SHAP değerleri hesaplar.
Doktora gösterilecek açıklama çıktısını üretir.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np
import shap

from config.settings import LABEL_NAMES, LABEL_DISPLAY_NAMES

# Matplotlib backend ayarı (headless sunucu için)
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt


class SHAPExplainer:
    """
    Binary Relevance modellerini SHAP ile açıklayan servis.
    Her label için ayrı TreeExplainer bulundurur.
    """

    def __init__(
        self,
        models: dict,               # {label: XGBClassifier}
        feature_names: list[str],
    ):
        self.feature_names = feature_names
        self.explainers = {}

        for label, model in models.items():
            self.explainers[label] = shap.TreeExplainer(model)

        print(f"[SHAP] {len(self.explainers)} explainer hazırlandı.")

    def explain_single(
        self,
        X: np.ndarray,
        top_n: int = 5,
    ) -> dict:
        """
        Tek bir örnek için SHAP açıklaması üret.

        Args:
            X: [1, n_features] şeklinde özellik matrisi (pipeline çıktısı).
            top_n: Gösterilecek en etkili özellik sayısı.

        Returns:
            Her label için SHAP analiz sözlüğü.
        """
        explanations = {}

        for label, explainer in self.explainers.items():
            shap_values = explainer.shap_values(X)

            # shap_values: [1, n_features] → [n_features]
            if isinstance(shap_values, list):
                # Binary classification: indeks 1 = pozitif sınıf
                sv = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
            else:
                sv = shap_values[0]

            # Özellik → SHAP değeri eşleştir (rule_* sentetik değişkenleri hariç tut)
            feature_shap = {k: v for k, v in zip(self.feature_names, sv.tolist()) if not k.startswith("rule_")}

            # Magnitude'e göre sırala (en etkili önce)
            sorted_factors = sorted(
                feature_shap.items(),
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:top_n]

            # İnsan okunabilir format
            formatted_factors = []
            for feat_name, shap_val in sorted_factors:
                direction = "karar yönünde" if shap_val > 0 else "karar aleyhine"
                formatted_factors.append({
                    "ozellik": _feature_display_name(feat_name),
                    "ozellik_kodu": feat_name,
                    "shap_degeri": round(float(shap_val), 4),
                    "etki": f"{'+' if shap_val > 0 else ''}{shap_val:.3f} ({direction})",
                })

            explanations[label] = {
                "label_adi": LABEL_DISPLAY_NAMES[label],
                "base_value": round(float(np.squeeze(explainer.expected_value)), 4),
                "top_faktorler": formatted_factors,
                "tum_shap": {k: round(v, 4) for k, v in feature_shap.items()},
            }

        return explanations

    def plot_waterfall(
        self,
        X: np.ndarray,
        label: str,
        save_path: Optional[str] = None,
        show: bool = False,
    ) -> None:
        """Waterfall plot — tek tahmin açıklaması."""
        explainer = self.explainers[label]
        shap_values = explainer(X)

        plt.figure(figsize=(10, 6))
        shap.plots.waterfall(shap_values[0], show=False)
        plt.title(f"SHAP Waterfall — {LABEL_DISPLAY_NAMES[label]}", fontsize=13)
        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"[SHAP] Waterfall plot kaydedildi: {save_path}")

        if show:
            plt.show()
        plt.close()

    def plot_summary(
        self,
        X_test: np.ndarray,
        label: str,
        save_path: Optional[str] = None,
        show: bool = False,
    ) -> None:
        """Summary plot — tüm test seti için global özellik önemi."""
        explainer = self.explainers[label]
        shap_values = explainer.shap_values(X_test)

        if isinstance(shap_values, list):
            sv = shap_values[1] if len(shap_values) > 1 else shap_values[0]
        else:
            sv = shap_values

        plt.figure(figsize=(10, 8))
        shap.summary_plot(
            sv, X_test,
            feature_names=self.feature_names,
            show=False,
        )
        plt.title(f"SHAP Global Önemi — {LABEL_DISPLAY_NAMES[label]}", fontsize=13)
        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"[SHAP] Summary plot kaydedildi: {save_path}")

        if show:
            plt.show()
        plt.close()


# ─── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

_FEATURE_DISPLAY_MAP = {
    "tirnak_tutulumu": "Tırnak tutulumu bulgusu",
    "sabah_turuklugu": "Klinik sabah tutukluğu (>30 dk)",
    "vki": "Vücut Kitle İndeksi (VKİ) tablosu",
    "ldl": "LDL Kolesterol seviyesi",
    "pasi_skoru": "Hesaplanan PASI Skoru",
    "sigara": "Aktif sigara kullanımı öyкüsü",
    "vki_obez": "Klinik Obezite Bulgusu (VKİ > 30)",
    "vki_asiri_obez": "Morbid Obezite Riski (VKİ > 35)",
    "ldl_yuksek": "Yüksek LDL Profili (>130 mg/dL)",
    "ldl_cok_yuksek": "Çok Yüksek LDL (>160 mg/dL)",
    "pasi_orta": "Orta Şiddetli Hastalık Tablosu (PASI 5-10)",
    "pasi_siddetli": "Şiddetli Hastalık Bulgusu (PASI > 10)",
    "dlqi": "Dermatoloji Yaşam Kalite İndeksi (DLQI)",
    "dlqi_yuksek": "Ciddi Yaşam Kalitesi Bozukluğu (DLQI > 10)",
    "bsa": "Vücut Yüzey Alanı (BSA) Tutulum Oranı",
    "bsa_genis": "Yaygın Vücut Tutulumu (BSA > %10)",
    "yas": "Hasta Yaş Faktörü",
    "genc_hasta": "Erken Başlangıçlı Psoriazis Profili (<40 yaş)",
    "eklem_bulgulari": "Artüler (Eklem) Bulguları",
    "tip_plak": "Psoriazis Tipi: Plak",
    "tip_gutat": "Psoriazis Tipi: Guttat",
    "tip_inverz": "Psoriazis Tipi: İnvers",
    "tip_pustular": "Psoriazis Tipi: Püstüler",
    "tip_eritrodermik": "Psoriazis Tipi: Eritrodermik",
    "tip_unknown": "Psoriazis Tipi: Bilinmiyor",
    "onceki_iyi": "Önceki Sistemik Tedavi Yanıtı: İyi",
    "onceki_kotu": "Önceki Sistemik Tedavi Yanıtı: Kötü",
    "onceki_yok": "Önceki Sistemik Tedavi: Yok",
}


def _feature_display_name(code: str) -> str:
    """Özellik kodunu Türkçe görüntü adına çevir."""
    return _FEATURE_DISPLAY_MAP.get(code, code.replace("_", " ").title())
