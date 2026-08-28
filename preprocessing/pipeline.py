"""
Preprocessing Pipeline
======================
Ham hasta verisi → Model giriş matrisi.

Pipeline adımları (sırayla):
  1. Validasyon (klinik aralık kontrolü)
  2. Eksik değer doldurma (imputation)
  3. Feature engineering
  4. Ölçeklendirme (StandardScaler — sayısal özellikler)
  5. Özellik sıralama (modelin beklediği sıraya koy)

Kullanım:
    pipeline = PreprocessingPipeline()
    pipeline.fit(train_patients)
    X = pipeline.transform(test_patients)
    pipeline.save("models/artifacts/v1.0/preprocessor.pkl")
"""

from __future__ import annotations

import json
import os
from typing import Optional

import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler

from feature_store.schema import PatientFeatures, PatientLabels
from preprocessing.feature_engineering import engineer_features, get_feature_names


# Sayısal özellikler ölçeklendirilir; binary ve flag'ler olduğu gibi bırakılır.
NUMERICAL_FEATURES = [
    "vki", "ldl", "pasi_skoru",
    "dlqi", "bsa", "yas",  # v2.0 (varsa)
]


class PreprocessingPipeline:
    """
    Scikit-learn benzeri API ile preprocessing pipeline.

    fit() → eğitim verisiyle istatistikleri (median vb.) hesapla
    transform() → yeni veriyi dönüştür
    fit_transform() → ikisini birden yap
    """

    def __init__(self, include_v2: bool = False):
        self.include_v2 = include_v2
        self.feature_names: list[str] = get_feature_names(include_v2)
        self.scaler = StandardScaler()
        self._numerical_indices: list[int] = []
        self._fitted = False

    def fit(self, patients: list[PatientFeatures]) -> "PreprocessingPipeline":
        """
        Eğitim verisiyle ölçeklendirici parametrelerini hesapla.
        Sadece train split üzerinde çağır!
        """
        X = self._to_matrix(patients)

        # Sayısal özellik indekslerini bul
        self._numerical_indices = [
            i for i, name in enumerate(self.feature_names)
            if name in NUMERICAL_FEATURES
        ]

        if self._numerical_indices:
            self.scaler.fit(X[:, self._numerical_indices])

        self._fitted = True
        return self

    def transform(self, patients: list[PatientFeatures]) -> np.ndarray:
        """Hastaları özellik matrisine dönüştür."""
        if not self._fitted:
            raise RuntimeError("Pipeline henüz fit edilmedi. Önce fit() çağır.")

        X = self._to_matrix(patients)

        # Sayısal sütunları ölçeklendir
        if self._numerical_indices:
            X[:, self._numerical_indices] = self.scaler.transform(
                X[:, self._numerical_indices]
            )

        return X

    def fit_transform(self, patients: list[PatientFeatures]) -> np.ndarray:
        return self.fit(patients).transform(patients)

    def transform_single(self, patient: PatientFeatures) -> np.ndarray:
        """Tek bir hastayı dönüştür (inference için)."""
        return self.transform([patient])

    def _to_matrix(self, patients) -> np.ndarray:
        """Hasta listesini ham float matrisine çevir (ölçeklendirme olmadan)."""
        if isinstance(patients, np.ndarray):
            return patients.copy()
            
        rows = []
        for patient in patients:
            feat_dict = engineer_features(patient, include_v2=self.include_v2)
            # Özellikleri tanımlı sıraya göre al; eksik olanları NaN yap
            row = [feat_dict.get(name, np.nan) for name in self.feature_names]
            rows.append(row)
        return np.array(rows, dtype=np.float64)

    @staticmethod
    def labels_to_matrix(labels: list[PatientLabels]) -> np.ndarray:
        """Label listesini [n_samples, 3] matrisine çevir."""
        return np.array([lbl.to_array() for lbl in labels], dtype=np.int32)

    def save(self, path: str) -> None:
        """Pipeline'ı diske kaydet."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self, path)
        print(f"[Pipeline] Kaydedildi: {path}")

    @classmethod
    def load(cls, path: str) -> "PreprocessingPipeline":
        """Diskten pipeline yükle."""
        pipeline = joblib.load(path)
        print(f"[Pipeline] Yüklendi: {path}")
        return pipeline

    def save_feature_names(self, path: str) -> None:
        """Özellik isimlerini JSON olarak kaydet (versiyonlama için)."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.feature_names, f, ensure_ascii=False, indent=2)
        print(f"[Pipeline] Özellik isimleri kaydedildi: {path}")
