"""
Unit Testler
============
Feature engineering, preprocessing pipeline ve model mantığı testleri.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from feature_store.schema import PatientFeatures, PatientLabels
from preprocessing.feature_engineering import engineer_features, get_feature_names
from preprocessing.pipeline import PreprocessingPipeline
from scripts.generate_synthetic_data import apply_rule_engine, generate_dataset


# ─── Test Hasta Fixture'ları ──────────────────────────────────────────────────

@pytest.fixture
def ftr_patient():
    """FTR önerisi gerektiren hasta."""
    return PatientFeatures(
        tirnak_tutulumu=True,
        sabah_turuklugu_30dk=True,
        vki=25.0, ldl=100.0, pasi_skoru=5.0, sigara=False,
    )


@pytest.fixture
def aile_patient():
    """Aile Hekimliği önerisi gerektiren hasta."""
    return PatientFeatures(
        tirnak_tutulumu=False,
        sabah_turuklugu_30dk=False,
        vki=35.0, ldl=160.0, pasi_skoru=3.0, sigara=True,
    )


@pytest.fixture
def sistemik_patient():
    """Sistemik Tedavi önerisi gerektiren hasta."""
    return PatientFeatures(
        tirnak_tutulumu=False,
        sabah_turuklugu_30dk=False,
        vki=24.0, ldl=110.0, pasi_skoru=15.0, sigara=False,
    )


@pytest.fixture
def normal_patient():
    """Hiçbir öneri gerektirmeyen hasta."""
    return PatientFeatures(
        tirnak_tutulumu=False,
        sabah_turuklugu_30dk=False,
        vki=22.0, ldl=100.0, pasi_skoru=3.0, sigara=False,
    )


# ─── Kural Motoru Testleri ────────────────────────────────────────────────────

class TestRuleEngine:
    def test_ftr_rule_tirnak(self, ftr_patient):
        label = apply_rule_engine(ftr_patient)
        assert label.ftr is True

    def test_ftr_rule_sabah_turuklugu(self):
        p = PatientFeatures(
            tirnak_tutulumu=False, sabah_turuklugu_30dk=True,
            vki=22.0, ldl=100.0, pasi_skoru=3.0, sigara=False,
        )
        assert apply_rule_engine(p).ftr is True

    def test_aile_rule_vki(self):
        p = PatientFeatures(
            tirnak_tutulumu=False, sabah_turuklugu_30dk=False,
            vki=31.0, ldl=100.0, pasi_skoru=3.0, sigara=False,
        )
        assert apply_rule_engine(p).aile_hekimligi is True

    def test_aile_rule_ldl(self):
        p = PatientFeatures(
            tirnak_tutulumu=False, sabah_turuklugu_30dk=False,
            vki=22.0, ldl=135.0, pasi_skoru=3.0, sigara=False,
        )
        assert apply_rule_engine(p).aile_hekimligi is True

    def test_sistemik_rule_pasi(self, sistemik_patient):
        assert apply_rule_engine(sistemik_patient).sistemik_tedavi is True

    def test_no_referral(self, normal_patient):
        label = apply_rule_engine(normal_patient)
        assert label.ftr is False
        assert label.aile_hekimligi is False
        assert label.sistemik_tedavi is False

    def test_multi_label(self, ftr_patient):
        """Hem FTR hem Aile Hekimliği gerektiren hasta."""
        ftr_patient.vki = 35.0  # Obez
        ftr_patient.ldl = 150.0  # Yüksek LDL
        label = apply_rule_engine(ftr_patient)
        assert label.ftr is True
        assert label.aile_hekimligi is True


# ─── Feature Engineering Testleri ────────────────────────────────────────────

class TestFeatureEngineering:
    def test_output_keys(self, ftr_patient):
        features = engineer_features(ftr_patient)
        expected_keys = get_feature_names(include_v2=False)
        assert set(expected_keys).issubset(set(features.keys()))

    def test_binary_features_are_zero_or_one(self, ftr_patient):
        features = engineer_features(ftr_patient)
        binary_keys = [
            "tirnak_tutulumu", "sabah_turuklugu", "sigara",
            "vki_obez", "vki_asiri_obez", "ldl_yuksek", "ldl_cok_yuksek",
            "pasi_orta", "pasi_siddetli", "eklem_risk",
            "rule_ftr", "rule_aile", "rule_sistemik",
        ]
        for key in binary_keys:
            val = features[key]
            assert val in (0.0, 1.0), f"{key}={val} 0 veya 1 olmalı"

    def test_pasi_thresholds(self):
        # Hafif PASI
        p1 = PatientFeatures(False, False, 22.0, 100.0, 3.0, False)
        f1 = engineer_features(p1)
        assert f1["pasi_orta"] == 0.0
        assert f1["pasi_siddetli"] == 0.0

        # Orta PASI
        p2 = PatientFeatures(False, False, 22.0, 100.0, 7.0, False)
        f2 = engineer_features(p2)
        assert f2["pasi_orta"] == 1.0
        assert f2["pasi_siddetli"] == 0.0

        # Şiddetli PASI
        p3 = PatientFeatures(False, False, 22.0, 100.0, 15.0, False)
        f3 = engineer_features(p3)
        assert f3["pasi_orta"] == 0.0
        assert f3["pasi_siddetli"] == 1.0

    def test_rule_features_match_rule_engine(self, ftr_patient):
        features = engineer_features(ftr_patient)
        label = apply_rule_engine(ftr_patient)
        assert features["rule_ftr"] == float(label.ftr)
        assert features["rule_aile"] == float(label.aile_hekimligi)
        assert features["rule_sistemik"] == float(label.sistemik_tedavi)

    def test_feature_count_v1(self, normal_patient):
        features = engineer_features(normal_patient, include_v2=False)
        expected_count = len(get_feature_names(include_v2=False))
        assert len(features) == expected_count


# ─── Preprocessing Pipeline Testleri ─────────────────────────────────────────

class TestPreprocessingPipeline:
    def test_fit_transform_shape(self):
        patients, _ = generate_dataset(n=100, seed=42)
        pipeline = PreprocessingPipeline()
        X = pipeline.fit_transform(patients)
        expected_features = len(get_feature_names(include_v2=False))
        assert X.shape == (100, expected_features)

    def test_transform_single(self, normal_patient):
        patients, _ = generate_dataset(n=50, seed=42)
        pipeline = PreprocessingPipeline()
        pipeline.fit(patients)
        X = pipeline.transform_single(normal_patient)
        assert X.shape[0] == 1
        assert X.shape[1] == len(get_feature_names(include_v2=False))

    def test_no_nan_in_v1_features(self, ftr_patient):
        """v1.0 özellikleri tüm değerler dolu olduğunda NaN içermemeli."""
        patients, _ = generate_dataset(n=50, seed=42)
        pipeline = PreprocessingPipeline()
        pipeline.fit(patients)
        X = pipeline.transform_single(ftr_patient)
        assert not np.any(np.isnan(X)), "v1.0 özelliklerinde NaN bulundu"

    def test_deterministic_transform(self, ftr_patient):
        """Aynı girdi her zaman aynı çıktı vermeli."""
        patients, _ = generate_dataset(n=50, seed=42)
        pipeline = PreprocessingPipeline()
        pipeline.fit(patients)
        X1 = pipeline.transform_single(ftr_patient)
        X2 = pipeline.transform_single(ftr_patient)
        np.testing.assert_array_equal(X1, X2)

    def test_labels_to_matrix(self):
        labels = [PatientLabels(True, False, True), PatientLabels(False, True, False)]
        y = PreprocessingPipeline.labels_to_matrix(labels)
        assert y.shape == (2, 3)
        np.testing.assert_array_equal(y[0], [1, 0, 1])
        np.testing.assert_array_equal(y[1], [0, 1, 0])


# ─── PatientFeatures Validasyon Testleri ─────────────────────────────────────

class TestPatientFeaturesValidation:
    def test_valid_patient_no_warnings(self):
        p = PatientFeatures(False, False, 25.0, 120.0, 5.0, False)
        assert len(p.validate()) == 0

    def test_invalid_vki_warning(self):
        p = PatientFeatures(False, False, 5.0, 120.0, 5.0, False)
        warnings = p.validate()
        assert any("VKİ" in w for w in warnings)

    def test_invalid_pasi_warning(self):
        p = PatientFeatures(False, False, 25.0, 120.0, 80.0, False)
        warnings = p.validate()
        assert any("PASI" in w for w in warnings)

    def test_to_dict(self, normal_patient):
        d = normal_patient.to_dict()
        assert isinstance(d, dict)
        assert "tirnak_tutulumu" in d
        assert "pasi_skoru" in d


# ─── Sentetik Veri Testleri ───────────────────────────────────────────────────

class TestSyntheticData:
    def test_generates_correct_count(self):
        patients, labels = generate_dataset(n=200, seed=42)
        assert len(patients) == 200
        assert len(labels) == 200

    def test_deterministic_with_same_seed(self):
        p1, l1 = generate_dataset(n=50, seed=42)
        p2, l2 = generate_dataset(n=50, seed=42)
        assert p1[0].vki == p2[0].vki
        assert l1[0].ftr == l2[0].ftr

    def test_different_seeds_differ(self):
        p1, _ = generate_dataset(n=50, seed=42)
        p2, _ = generate_dataset(n=50, seed=123)
        assert not all(p1[i].vki == p2[i].vki for i in range(50))
