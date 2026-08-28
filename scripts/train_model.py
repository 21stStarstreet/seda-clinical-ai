"""
Model Eğitim CLI
================
Sentetik veya gerçek veriyle modeli eğitir ve kaydeder.

Kullanım:
    # Sentetik veriyle (geliştirme):
    python scripts/train_model.py --synthetic --n 2000

    # Gerçek veriyle:
    python scripts/train_model.py --data data/processed/patients.parquet

    # Hiperparametre optimizasyonusuz (hızlı test):
    python scripts/train_model.py --synthetic --no-optimize
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings, set_global_seed
from models.trainer import (
    generate_dataset,
    to_dataframe,
    load_from_parquet,
    load_from_csv,
    dataframe_to_objects,
    stratified_split,
    train_all_classifiers,
    save_models,
)
from models.evaluator import (
    evaluate_model,
    print_evaluation_report,
    save_evaluation_report,
    check_target_achieved,
)
from preprocessing.pipeline import PreprocessingPipeline


def main():
    parser = argparse.ArgumentParser(description="Psoriazis CDSS modeli eğit.")

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--synthetic", action="store_true", help="Sentetik veri üret ve kullan")
    source.add_argument("--data", type=str, help="Veri dosyası yolu (.parquet veya .csv)")

    parser.add_argument("--n", type=int, default=2000, help="Sentetik veri boyutu (default: 2000)")
    parser.add_argument("--noise", type=float, default=0.02, help="Gürültü oranı (default: 0.02)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--version", type=str, default="v1.0", help="Model versiyonu (default: v1.0)")
    parser.add_argument("--model-dir", type=str, default="models/artifacts", help="Model kayıt dizini")
    parser.add_argument("--no-optimize", action="store_true", help="Optuna optimizasyonunu atla")
    parser.add_argument("--trials", type=int, default=50, help="Optuna trial sayısı (default: 50)")

    args = parser.parse_args()

    set_global_seed(args.seed)

    print("\n" + "=" * 60)
    print("PSORİAZİS CDSS — MODEL EĞİTİMİ")
    print("=" * 60)

    # ── Veri yükle ────────────────────────────────────────────────
    if args.synthetic:
        print(f"\n[Veri] {args.n} sentetik hasta üretiliyor...")
        patients, labels = generate_dataset(n=args.n, seed=args.seed, noise_rate=args.noise)
        df = to_dataframe(patients, labels)
        print(f"[Veri] Üretildi: {len(df)} kayıt")
    else:
        data_path = args.data
        print(f"\n[Veri] Yükleniyor: {data_path}")
        if data_path.endswith(".parquet"):
            patients, labels = load_from_parquet(data_path)
        else:
            patients, labels = load_from_csv(data_path)
        print(f"[Veri] Yüklendi: {len(patients)} kayıt")

    # ── Preprocessing Pipeline ────────────────────────────────────
    # ── Preprocessing Pipeline ────────────────────────────────────
    print("\n[Pipeline] Preprocessing pipeline hazırlanıyor...")
    pipeline = PreprocessingPipeline(include_v2=True)

    # ── Split ─────────────────────────────────────────────────────
    import numpy as np
    y = np.array([lbl.to_array() for lbl in labels])

    # Geçici ham matris (split için)
    X_raw = pipeline._to_matrix(patients)

    X_train_raw, X_val_raw, X_test_raw, y_train_arr, y_val_arr, y_test_arr = stratified_split(
        X_raw, y, test_size=0.15, val_size=0.15, seed=args.seed
    )

    # DataFrame'leri fit edip matrise dönüştür
    pipeline.fit(X_train_raw)
    X_train = pipeline.transform(X_train_raw)
    X_val = pipeline.transform(X_val_raw)
    X_test = pipeline.transform(X_test_raw)

    print(f"[Split] Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    # ── Model Eğitimi ─────────────────────────────────────────────
    print("\n[Model] Classifier'lar eğitiliyor...")
    models = train_all_classifiers(
        X_train, y_train_arr,
        X_val, y_val_arr,
        optimize=not args.no_optimize,
        n_trials=args.trials,
    )

    # ── Değerlendirme ─────────────────────────────────────────────
    print("\n[Değerlendirme] Test seti üzerinde değerlendiriliyor...")
    report = evaluate_model(models, X_test, y_test_arr)
    print_evaluation_report(report)

    # Raporu kaydet
    report_path = f"reports/evaluation_{args.version}.json"
    save_evaluation_report(report, report_path)

    # Hedef kontrolü
    target_ok = check_target_achieved(report)

    # ── Model Kaydet ──────────────────────────────────────────────
    print(f"\n[Kayıt] Modeller kaydediliyor → {args.model_dir}/{args.version}")
    save_models(
        models=models,
        pipeline=pipeline,
        save_dir=args.model_dir,
        version=args.version,
        performance={
            label: {
                "f1": report[label]["f1"],
                "auc": report[label]["auc_roc"],
            }
            for label in ["ftr", "aile_hekimligi", "sistemik_tedavi"]
        },
    )

    print("\n[Eğitim] ✅ Tamamlandı!")
    if not target_ok:
        print("[Uyarı] Hedef F1 ≥ 0.98 bazı label'lar için sağlanamadı.")
        print("  → Daha fazla veri veya hiperparametre ayarı gerekebilir.")


if __name__ == "__main__":
    main()
