"""
Model Eğitici
=============
Binary Relevance stratejisi ile 3 ayrı XGBoost sınıflandırıcı eğitir.
Her label (FTR, Aile Hekimliği, Sistemik Tedavi) için bağımsız model.

Eğitim akışı:
  1. Sentetik / gerçek veriyi yükle
  2. Preprocessing pipeline'ını fit et
  3. Multi-label stratified split
  4. Optuna ile hiperparametre optimizasyonu
  5. Final model eğitimi (en iyi parametrelerle)
  6. Modelleri kaydet

Kullanım:
    python scripts/train_model.py --data data/synthetic/patients.parquet
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score, precision_score, recall_score
from xgboost import XGBClassifier

# Optuna log seviyesini azalt
optuna.logging.set_verbosity(optuna.logging.WARNING)

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings, set_global_seed, LABEL_NAMES
from feature_store.schema import PatientFeatures, PatientLabels
from preprocessing.pipeline import PreprocessingPipeline
from scripts.generate_synthetic_data import to_dataframe, generate_dataset


# ─── XGBoost Temel Parametreler ───────────────────────────────────────────────

BASE_XGB_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "tree_method": "hist",       # Hızlı eğitim
    "device": "cpu",
    "seed": settings.random_seed,
    "verbosity": 0,
    "n_jobs": 1,                 # Deterministik çıktı için sabit thread
}

# Küçük veri için güvenli başlangıç parametreleri (overfitting önleme)
SAFE_XGB_PARAMS = {
    **BASE_XGB_PARAMS,
    "max_depth": 3,
    "learning_rate": 0.05,
    "n_estimators": 300,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "alpha": 0.1,                # L1
    "lambda": 1.0,               # L2
    "early_stopping_rounds": 30,
}


# ─── Veri Yükleme ─────────────────────────────────────────────────────────────

def load_from_parquet(path: str) -> tuple[list[PatientFeatures], list[PatientLabels]]:
    """Parquet dosyasından hasta ve etiket yükle."""
    df = pd.read_parquet(path)
    return dataframe_to_objects(df)


def load_from_csv(path: str) -> tuple[list[PatientFeatures], list[PatientLabels]]:
    """CSV dosyasından hasta ve etiket yükle."""
    df = pd.read_csv(path)
    return dataframe_to_objects(df)


def dataframe_to_objects(
    df: pd.DataFrame,
) -> tuple[list[PatientFeatures], list[PatientLabels]]:
    """DataFrame → (PatientFeatures listesi, PatientLabels listesi).
    
    Hem eski format (label_ftr, label_aile_hekimligi, label_sistemik_tedavi)
    hem de yeni ETL formatı (ftr, aile_hekimligi, sistemik_tedavi) desteklenir.
    """
    patients = []
    labels = []

    # Etiket sütun isimlerini otomatik belirle (eski vs yeni format)
    if "label_ftr" in df.columns:
        col_ftr, col_aile, col_sistemik = "label_ftr", "label_aile_hekimligi", "label_sistemik_tedavi"
    else:
        col_ftr, col_aile, col_sistemik = "ftr", "aile_hekimligi", "sistemik_tedavi"

    for _, row in df.iterrows():
        patient = PatientFeatures(
            tirnak_tutulumu=bool(row["tirnak_tutulumu"]),
            sabah_turuklugu_30dk=bool(row["sabah_turuklugu_30dk"]),
            vki=float(row["vki"]),
            ldl=float(row["ldl"]),
            pasi_skoru=float(row["pasi_skoru"]),
            sigara=bool(row["sigara"]),
            hasta_id=str(row.get("hasta_id", "")),
            # Opsiyonel v2.0 alanları (varsa yükle)
            dlqi=float(row["dlqi"]) if "dlqi" in df.columns and pd.notna(row.get("dlqi")) else None,
            bsa=float(row["bsa"]) if "bsa" in df.columns and pd.notna(row.get("bsa")) else None,
            yas=int(row["yas"]) if "yas" in df.columns and pd.notna(row.get("yas")) else None,
            hastalik_suresi_ay=int(row["hastalik_suresi_ay"]) if "hastalik_suresi_ay" in df.columns and pd.notna(row.get("hastalik_suresi_ay")) else None,
        )
        label = PatientLabels(
            ftr=bool(row[col_ftr]),
            aile_hekimligi=bool(row[col_aile]),
            sistemik_tedavi=bool(row[col_sistemik]),
        )
        patients.append(patient)
        labels.append(label)

    return patients, labels


# ─── Train/Test Split ─────────────────────────────────────────────────────────

def stratified_split(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.15,
    val_size: float = 0.15,
    seed: int = 42,
) -> tuple[np.ndarray, ...]:
    """
    Multi-label stratified train/val/test split.

    iterstrat kütüphanesi mevcut değilse sklearn fallback kullanılır.
    """
    try:
        from iterstrat.ml_stratifiers import MultilabelStratifiedShuffleSplit

        # Train+Val / Test split
        msss = MultilabelStratifiedShuffleSplit(
            n_splits=1, test_size=test_size, random_state=seed
        )
        train_val_idx, test_idx = next(msss.split(X, y))
        X_train_val, X_test = X[train_val_idx], X[test_idx]
        y_train_val, y_test = y[train_val_idx], y[test_idx]

        # Train / Val split
        val_relative = val_size / (1 - test_size)
        msss2 = MultilabelStratifiedShuffleSplit(
            n_splits=1, test_size=val_relative, random_state=seed
        )
        train_idx, val_idx = next(msss2.split(X_train_val, y_train_val))
        X_train = X_train_val[train_idx]
        X_val = X_train_val[val_idx]
        y_train = y_train_val[train_idx]
        y_val = y_train_val[val_idx]

    except ImportError:
        print("[UYARI] iterstrat bulunamadı, sklearn ShuffleSplit kullanılıyor.")
        from sklearn.model_selection import train_test_split

        X_train_val, X_test, y_train_val, y_test = train_test_split(
            X, y, test_size=test_size, random_state=seed
        )
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_val, y_train_val,
            test_size=val_size / (1 - test_size),
            random_state=seed,
        )

    print(f"[Split] Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
    return X_train, X_val, X_test, y_train, y_val, y_test


# ─── Optuna Optimizasyon ──────────────────────────────────────────────────────

def optimize_hyperparams(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    label_idx: int,
    n_trials: int = 50,
    seed: int = 42,
) -> dict:
    """
    Tek bir label için Optuna ile hiperparametre optimizasyonu.
    Val seti üzerinde AUC maximizasyonu.
    """
    y_tr = y_train[:, label_idx]
    y_vl = y_val[:, label_idx]

    # Sınıf dengesizliği
    pos_rate = y_tr.mean()
    scale_pos_weight = (1 - pos_rate) / pos_rate if pos_rate > 0 else 1.0

    def objective(trial: optuna.Trial) -> float:
        params = {
            **BASE_XGB_PARAMS,
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "alpha": trial.suggest_float("alpha", 0.0, 1.0),
            "lambda": trial.suggest_float("lambda", 0.5, 3.0),
            "scale_pos_weight": scale_pos_weight,
        }

        model = XGBClassifier(**params)
        model.fit(
            X_train, y_tr,
            eval_set=[(X_val, y_vl)],
            verbose=False,
        )

        y_prob = model.predict_proba(X_val)[:, 1]
        # Tek sınıf varsa roc_auc NaN döner — F1'e fallback yap
        if len(np.unique(y_vl)) < 2:
            from sklearn.metrics import f1_score
            y_pred = (y_prob >= 0.5).astype(int)
            return f1_score(y_vl, y_pred, zero_division=0)
        return roc_auc_score(y_vl, y_prob)

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best = study.best_params
    best.update(BASE_XGB_PARAMS)
    best["scale_pos_weight"] = scale_pos_weight
    return best


# ─── Model Eğitimi ────────────────────────────────────────────────────────────

def train_single_classifier(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    label_idx: int,
    params: dict,
) -> XGBClassifier:
    """Tek bir label için XGBoost classifier eğit."""
    y_tr = y_train[:, label_idx]
    y_vl = y_val[:, label_idx]

    # Sınıf dengesizliğini otomatik düzelt
    pos_rate = y_tr.mean()
    if 0 < pos_rate < 1:
        scale_pos_weight = (1 - pos_rate) / pos_rate
        params = {**params, "scale_pos_weight": scale_pos_weight}
        print(f"    scale_pos_weight={scale_pos_weight:.2f} (pozitif oran: %{pos_rate*100:.1f})")

    model = XGBClassifier(**params)
    model.fit(
        X_train, y_tr,
        eval_set=[(X_val, y_vl)],
        verbose=False,
    )
    return model


def train_all_classifiers(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    optimize: bool = True,
    n_trials: int = 50,
) -> dict[str, XGBClassifier]:
    """
    3 label için tüm classifiers'ları eğit.

    Returns:
        {'ftr': model, 'aile_hekimligi': model, 'sistemik_tedavi': model}
    """
    models = {}

    for i, label in enumerate(LABEL_NAMES):
        print(f"\n[Eğitim] {label.upper()} classifier'ı eğitiliyor...")

        if optimize:
            print(f"  Optuna optimizasyonu ({n_trials} trial)...")
            best_params = optimize_hyperparams(
                X_train, y_train, X_val, y_val,
                label_idx=i, n_trials=n_trials,
            )
            print(f"  En iyi params: max_depth={best_params.get('max_depth')}, "
                  f"lr={best_params.get('learning_rate', 0):.4f}")
        else:
            best_params = SAFE_XGB_PARAMS.copy()

        model = train_single_classifier(
            X_train, y_train, X_val, y_val,
            label_idx=i, params=best_params,
        )
        models[label] = model
        print(f"  [OK] {label} modeli hazır.")

    return models


# ─── Model Kaydetme ───────────────────────────────────────────────────────────

def save_models(
    models: dict[str, XGBClassifier],
    pipeline: PreprocessingPipeline,
    save_dir: str,
    version: str,
    performance: dict,
) -> None:
    """Modelleri ve metadata'yı diske kaydet."""
    version_dir = Path(save_dir) / version
    version_dir.mkdir(parents=True, exist_ok=True)

    # Her model için
    for label, model in models.items():
        model_path = version_dir / f"model_{label}.pkl"
        joblib.dump(model, model_path)
        print(f"[Kayıt] {model_path}")

    # Preprocessing pipeline
    pipeline.save(str(version_dir / "preprocessor.pkl"))

    # Özellik isimleri
    pipeline.save_feature_names(str(version_dir / "feature_names.json"))

    # Metadata
    metadata = {
        "schema_version": "1.0",
        "model_version": version,
        "training_date": datetime.now().isoformat(),
        "feature_names": pipeline.feature_names,
        "n_features": len(pipeline.feature_names),
        "model_type": "xgboost_binary_relevance",
        "labels": LABEL_NAMES,
        "performance": performance,
    }

    with open(version_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"[Kayıt] {version_dir / 'metadata.json'}")

    # Production symlink (Unix)
    prod_link = Path(save_dir) / "production"
    if prod_link.exists() or prod_link.is_symlink():
        prod_link.unlink()
    try:
        prod_link.symlink_to(version, target_is_directory=True)
        print(f"[Symlink] production → {version}")
    except OSError:
        print(f"[Uyarı] Symlink oluşturulamadı (Windows?). Manuel ayarlayın: {version}")
