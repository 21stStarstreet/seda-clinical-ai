"""
Model Değerlendirici
====================
Multi-label performans metrikleri.

Hem per-label hem overall metrikler üretir.
Test seti üzerinde çalıştırılır — sadece final değerlendirmede.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    hamming_loss,
    accuracy_score,
    confusion_matrix,
    classification_report,
)
from xgboost import XGBClassifier

from config.settings import LABEL_NAMES, LABEL_DISPLAY_NAMES


def evaluate_model(
    models: dict[str, XGBClassifier],
    X_test: np.ndarray,
    y_test: np.ndarray,
    thresholds: Optional[dict[str, float]] = None,
) -> dict:
    """
    Test seti üzerinde kapsamlı değerlendirme.

    Args:
        models: {'ftr': model, 'aile_hekimligi': model, 'sistemik_tedavi': model}
        X_test: Test özellik matrisi
        y_test: Gerçek etiketler [n_samples, 3]
        thresholds: Per-label olasılık eşiği (default 0.5)

    Returns:
        Kapsamlı metrik sözlüğü
    """
    if thresholds is None:
        thresholds = {label: 0.5 for label in LABEL_NAMES}

    # Her label için tahmin
    y_prob = np.zeros_like(y_test, dtype=float)
    y_pred = np.zeros_like(y_test, dtype=int)

    for i, label in enumerate(LABEL_NAMES):
        model = models[label]
        prob = model.predict_proba(X_test)[:, 1]
        y_prob[:, i] = prob
        y_pred[:, i] = (prob >= thresholds[label]).astype(int)

    report = {}

    # ── Per-label metrikler ────────────────────────────────────────────────────
    for i, label in enumerate(LABEL_NAMES):
        yt = y_test[:, i]
        yp = y_pred[:, i]
        yprob = y_prob[:, i]

        cm = confusion_matrix(yt, yp)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

        # AUC — tek sınıf varsa (tüm test etiketi 0 ya da hepsi 1) roc_auc_score
        # ValueError fırlatır ve metadata'ya NaN yazılır. Bu durumu açıkça ele alıyoruz.
        unique_classes = np.unique(yt)
        if len(unique_classes) < 2:
            auc_roc = None  # Hesaplanamaz — test setinde yalnızca 1 sınıf mevcut
        else:
            try:
                auc_roc = round(float(roc_auc_score(yt, yprob)), 4)
            except Exception:
                auc_roc = None

        report[label] = {
            "display_name": LABEL_DISPLAY_NAMES[label],
            "f1": round(float(f1_score(yt, yp, zero_division=0)), 4),
            "precision": round(float(precision_score(yt, yp, zero_division=0)), 4),
            "recall": round(float(recall_score(yt, yp, zero_division=0)), 4),
            "auc_roc": auc_roc,
            "threshold": thresholds[label],
            "confusion_matrix": {
                "tn": int(tn), "fp": int(fp),
                "fn": int(fn), "tp": int(tp),
            },
            "n_positive": int(yt.sum()),
            "n_negative": int((1 - yt).sum()),
        }

    # ── Overall metrikler ─────────────────────────────────────────────────────
    report["overall"] = {
        "exact_match_accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "hamming_loss": round(float(hamming_loss(y_test, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "micro_f1": round(float(f1_score(y_test, y_pred, average="micro", zero_division=0)), 4),
        "n_test_samples": len(y_test),
    }

    return report


def print_evaluation_report(report: dict) -> None:
    """Değerlendirme raporunu terminale güzel formatta yazdır."""
    print("\n" + "=" * 70)
    print("MODEL PERFORMANS RAPORU")
    print("=" * 70)

    for label in LABEL_NAMES:
        r = report[label]
        print(f"\n📊 {r['display_name']}")
        print(f"   F1 Score  : {r['f1']:.4f} {'✅' if r['f1'] >= 0.98 else '⚠️'}")
        print(f"   Precision : {r['precision']:.4f}")
        print(f"   Recall    : {r['recall']:.4f}")
        
        if r['auc_roc'] is not None:
            print(f"   AUC-ROC   : {r['auc_roc']:.4f} {'✅' if r['auc_roc'] >= 0.98 else '⚠️'}")
        else:
            print(f"   AUC-ROC   : N/A (Tek Sınıf)")

        cm = r["confusion_matrix"]
        print(f"   TN={cm['tn']} FP={cm['fp']} FN={cm['fn']} TP={cm['tp']}")

    ov = report["overall"]
    print(f"\n📈 GENEL")
    print(f"   Exact Match Accuracy : {ov['exact_match_accuracy']:.4f}")
    print(f"   Hamming Loss         : {ov['hamming_loss']:.4f} {'✅' if ov['hamming_loss'] <= 0.02 else '⚠️'}")
    print(f"   Macro F1             : {ov['macro_f1']:.4f}")
    print(f"   Test Örnek Sayısı    : {ov['n_test_samples']}")
    print("=" * 70)


def save_evaluation_report(report: dict, path: str) -> None:
    """Raporu JSON olarak kaydet."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[Değerlendirme] Rapor kaydedildi: {path}")


def check_target_achieved(report: dict, target_f1: float = 0.98) -> bool:
    """Hedef F1 skoruna ulaşıldı mı kontrol et."""
    all_pass = all(
        report[label]["f1"] >= target_f1
        for label in LABEL_NAMES
    )
    if all_pass:
        print(f"\n✅ Hedef F1 ≥ {target_f1} TÜM LABEL'LAR İÇİN SAĞLANDI!")
    else:
        failing = [
            label for label in LABEL_NAMES
            if report[label]["f1"] < target_f1
        ]
        print(f"\n⚠️  Hedef F1 ≥ {target_f1} SAĞLANAMADI: {failing}")
    return all_pass
