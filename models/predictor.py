"""
Model Predictor — Inference Servisi
====================================
Kaydedilmiş modelleri yükler ve yeni hastalar için tahmin üretir.
API katmanı bu sınıfı kullanır.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from xgboost import XGBClassifier

from config.settings import settings, LABEL_NAMES, LABEL_DISPLAY_NAMES
from feature_store.schema import PatientFeatures, PatientLabels
from preprocessing.pipeline import PreprocessingPipeline


class PredictionResult:
    """Tek bir tahmin sonucu."""

    def __init__(
        self,
        labels: PatientLabels,
        probabilities: dict[str, float],
        model_version: str,
    ):
        self.labels = labels
        self.probabilities = probabilities
        self.model_version = model_version

    def to_dict(self) -> dict:
        return {
            "tahmin": {
                LABEL_DISPLAY_NAMES[label]: {
                    "karar": getattr(self.labels, label),
                    "olasilik": round(self.probabilities[label], 4),
                }
                for label in LABEL_NAMES
            },
            "aktif_birimler": [
                LABEL_DISPLAY_NAMES[label]
                for label in LABEL_NAMES
                if getattr(self.labels, label)
            ],
            "model_versiyonu": self.model_version,
        }


class Predictor:
    """
    Kaydedilmiş XGBoost modellerini yükleyip inference yapan servis.

    Kullanım:
        predictor = Predictor.load("models/artifacts/production")
        result = predictor.predict(patient)
        print(result.to_dict())
    """

    def __init__(
        self,
        models: dict[str, XGBClassifier],
        pipeline: PreprocessingPipeline,
        thresholds: dict[str, float],
        version: str,
    ):
        self.models = models
        self.pipeline = pipeline
        self.thresholds = thresholds
        self.version = version

    def predict(self, patient: PatientFeatures) -> PredictionResult:
        """
        Tek bir hasta için tahmin üret.

        Args:
            patient: Ham hasta özellikleri.

        Returns:
            PredictionResult — label kararları + olasılıklar.
        """
        # Validasyon uyarıları (loglama için)
        warnings = patient.validate()
        for w in warnings:
            logging.getLogger("uvicorn.error").warning(f"[Predictor] {w}")

        # Feature transformation
        X = self.pipeline.transform_single(patient)

        # Her label için olasılık
        probabilities = {}
        for label in LABEL_NAMES:
            prob = self.models[label].predict_proba(X)[0, 1]
            probabilities[label] = float(prob)

        # Threshold uygula
        labels = PatientLabels(
            ftr=probabilities["ftr"] >= self.thresholds["ftr"],
            aile_hekimligi=probabilities["aile_hekimligi"] >= self.thresholds["aile_hekimligi"],
            sistemik_tedavi=probabilities["sistemik_tedavi"] >= self.thresholds["sistemik_tedavi"],
        )

        return PredictionResult(
            labels=labels,
            probabilities=probabilities,
            model_version=self.version,
        )

    def predict_batch(self, patients: list[PatientFeatures]) -> list[PredictionResult]:
        """Birden fazla hasta için toplu tahmin."""
        return [self.predict(p) for p in patients]

    @classmethod
    def load(cls, model_dir: str) -> "Predictor":
        """
        Kaydedilmiş modelleri diskten yükle.

        Args:
            model_dir: Model dizini (örn. 'models/artifacts/production')
        """
        model_path = Path(model_dir)

        # Metadata
        with open(model_path / "metadata.json", encoding="utf-8") as f:
            metadata = json.load(f)

        version = metadata["model_version"]

        # Modeller
        models = {}
        for label in LABEL_NAMES:
            model_file = model_path / f"model_{label}.pkl"
            models[label] = joblib.load(model_file)

        # Pipeline
        pipeline = PreprocessingPipeline.load(str(model_path / "preprocessor.pkl"))

        # Thresholds (metadata'da varsa kullan, yoksa 0.5)
        thresholds = metadata.get(
            "thresholds", {label: 0.5 for label in LABEL_NAMES}
        )

        logging.getLogger("uvicorn.error").info(f"[Predictor] Model v{version} yüklendi ({len(LABEL_NAMES)} classifier).")
        return cls(models, pipeline, thresholds, version)

    @classmethod
    def load_safe(cls, model_dir: str) -> Optional["Predictor"]:
        """Model yoksa None döner (API başlangıcında güvenli yükleme için)."""
        try:
            return cls.load(model_dir)
        except Exception as e:
            logging.getLogger("uvicorn.error").error(f"[Predictor] Model yüklenemedi: {model_dir}. Hata: {e}")
            return None
