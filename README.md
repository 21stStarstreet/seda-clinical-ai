# Psoriazis CDSS

Psoriazis hastalarını doğru uzmana yönlendiren, makine öğrenmesi tabanlı **Klinik Karar Destek Sistemi**.

## Mimari

```
Ham Hasta Verisi → Feature Engineering → XGBoost (×3) → SHAP → LLM (Gemini) → Doktor
```

**Çıktı Sınıfları (Multi-label):**
- 🏃 Fizik Tedavi ve Rehabilitasyon (FTR)
- 🏥 Aile Hekimliği
- 💊 Sistemik Tedavi

## Hızlı Başlangıç

### 1. Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Ortam Değişkenleri

```bash
cp .env.example .env
# .env dosyasını düzenle — GEMINI_API_KEY'i ekle
```

### 3. Sentetik Veri Üret

```bash
python scripts/generate_synthetic_data.py --n 2000 --output data/synthetic/patients.parquet
```

### 4. Modeli Eğit

```bash
# Hızlı test (optimizasyonsuz):
python scripts/train_model.py --synthetic --n 2000 --no-optimize

# Tam eğitim (Optuna ile, ~10 dk):
python scripts/train_model.py --synthetic --n 2000 --trials 100
```

### 5. API'yi Başlat

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API dokümantasyonu: http://localhost:8000/docs

### 6. Testleri Çalıştır

```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

## Örnek API Kullanımı

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "hasta_id": "PSO-001",
    "tirnak_tutulumu": true,
    "sabah_turuklugu_30dk": true,
    "vki": 33.2,
    "ldl": 145.0,
    "pasi_skoru": 7.2,
    "sigara": true
  }'
```

## Proje Yapısı

```
dermatology_project/
├── feature_store/      # Hasta özellik şeması (PatientFeatures)
├── preprocessing/      # Feature engineering + pipeline
├── models/             # XGBoost trainer, predictor, evaluator
├── explainability/     # SHAP açıklamaları
├── llm/                # Gemini açıklama servisi
├── api/                # FastAPI uygulaması
├── audit/              # SQLite audit log
├── scripts/            # CLI araçları
├── tests/              # Unit testler
├── data/               # Veri dosyaları (git'e eklenmez)
└── config/             # Ayarlar ve eşik değerleri
```

## Yeni Parametre Ekleme (v2.0)

1. `feature_store/schema.py` → `PatientFeatures` dataclass'ına `Optional` alan ekle
2. `preprocessing/feature_engineering.py` → `engineer_features()` fonksiyonuna işle
3. `config/settings.py` → Yeni klinik eşik değeri ekle (gerekirse)
4. Modeli yeniden eğit: `python scripts/train_model.py --synthetic --version v2.0`

## Teknoloji Stack

| Katman | Teknoloji |
|--------|-----------|
| ML Modeli | XGBoost (Binary Relevance) |
| Optimizasyon | Optuna |
| Açıklanabilirlik | SHAP TreeExplainer |
| LLM | Google Gemini Flash |
| API | FastAPI |
| Veritabanı | SQLite / PostgreSQL |
| Dil | Python 3.10+ |

## Geliştirme Fazları

- **Faz 1** ✅ Altyapı + Sentetik Veri + Model + API
- **Faz 2** 🔄 Gerçek Hasta Verisi Entegrasyonu
- **Faz 3** 📅 Klinik Parametre Genişletmesi (v2.0)
- **Faz 4** 📅 Prodüksiyon (KVKK uyumu, auth, monitoring)
