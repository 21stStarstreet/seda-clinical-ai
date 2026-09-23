# 🩺 SEDA (Sedef Destek Algoritması)
### Psoriasis Vulgaris Tedavi Protokolü & Çok Disiplinli Sevk Karar Destek Sistemi

<p align="center">
  <!-- Diller & Framework'ler -->
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-REST_API-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/C%23-12.0-239120?style=flat&logo=c-sharp&logoColor=white" alt="C#" />
  <img src="https://img.shields.io/badge/.NET-8.0-512BD4?style=flat&logo=dotnet&logoColor=white" alt="Dotnet" />
  <img src="https://img.shields.io/badge/Blazor-Interactive_Server-512BD4?style=flat&logo=blazor&logoColor=white" alt="Blazor" />
</p>

<p align="center">
  <!-- Yapay Zekâ & Makine Öğrenmesi -->
  <img src="https://img.shields.io/badge/XGBoost-Binary_Relevance-EB5424?style=flat" alt="XGBoost" />
  <img src="https://img.shields.io/badge/SHAP-TreeExplainer-FF6F00?style=flat" alt="SHAP" />
  <img src="https://img.shields.io/badge/Google_Gemini-1.5_Flash-8E75C2?style=flat&logo=google-gemini&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/Scikit_Learn-Pipeline-F7931E?style=flat&logo=scikit-learn&logoColor=white" alt="Scikit-Learn" />
</p>

<p align="center">
  <!-- Güvenlik, Veri & UI -->
  <img src="https://img.shields.io/badge/JWT-OAuth2_Bearer-black?style=flat&logo=json-web-tokens&logoColor=white" alt="JWT" />
  <img src="https://img.shields.io/badge/BCrypt-Password_Hash-4A154B?style=flat" alt="BCrypt" />
  <img src="https://img.shields.io/badge/Cryptography-AES--128_Fernet-00599C?style=flat" alt="Fernet" />
  <img src="https://img.shields.io/badge/SQLite-Encrypted_Audit-003B57?style=flat&logo=sqlite&logoColor=white" alt="SQLite" />
</p>

---

# Faz 1 — Adım Adım Uygulama Kaydı

> **Tarih**: 29 Temmuz 2026  
> **Amaç**: Psoriazis CDSS Faz 1 altyapısını sıfırdan kurmak  
> **Ortam**: Python 3.13.9, macOS, proje dizini: `~/Projects/dermatology_project`

---

## Adım 1 — Mimari Kararı

Kod yazmadan önce şu temel kararlar alındı:

| Karar | Seçim | Gerekçe |
|-------|-------|---------|
| Multi-label strateji | Binary Relevance | Her çıktı klinik olarak bağımsız karar |
| ML modeli | XGBoost | Küçük tabular veri + SHAP uyumluluğu |
| SHAP türü | TreeExplainer | XGBoost için hızlı, doğru |
| LLM | Gemini Flash | Hız + maliyet + Türkçe kalitesi |
| API | FastAPI | Python native, async, otomatik dokümantasyon |
| Veritabanı | SQLite (→ PostgreSQL) | Geliştirmede basit, üretimde taşınabilir |

---

## Adım 2 — Dizin Yapısını Oluşturma

```bash
mkdir -p data/{raw,processed,synthetic,external}
mkdir -p feature_store preprocessing
mkdir -p models/{artifacts/v1.0}
mkdir -p explainability llm api/{routes}
mkdir -p audit notebooks tests scripts config reports
```

**Sonuç:** Tüm modüler klasörler oluşturuldu.

---

## Adım 3 — Proje Yapılandırma Dosyaları

### 3.1 pyproject.toml

Projenin bağımlılıklarını tanımlar. Temel gruplar:

- **core-ml**: numpy, pandas, scikit-learn, xgboost, lightgbm, optuna
- **explainability**: shap, matplotlib, seaborn
- **api**: fastapi, uvicorn
- **llm**: google-generativeai
- **storage**: sqlalchemy, alembic
- **testing**: pytest, pytest-cov, httpx

> `iterstrat` paketi Python 3.13'te mevcut değildi.
> trainer.py'ye sklearn fallback eklendi.

### 3.2 .env.example

```
GEMINI_API_KEY=...
DATABASE_URL=sqlite:///./audit.db
API_HOST=0.0.0.0
API_PORT=8000
LLM_ENABLED=true
RANDOM_SEED=42
```

### 3.3 .gitignore

Kritik kurallar:
- `data/raw/` ve `data/processed/` → asla git'e girmiyor (KVKK)
- `*.pkl`, `*.joblib` → büyük model artifact'ları hariç
- `.env` → API key'ler hariç

---

## Adım 4 — config/settings.py

**Amaç:** Tüm sabit değerlerin merkezi yönetimi.

İçerik:
- `Settings(BaseSettings)` — pydantic-settings ile .env okuma
- `ClinicalThresholds` — doktor onaylı klinik eşik değerleri:
  - `VKI_OBEZ = 30.0`
  - `LDL_YUKSEK = 130.0` mg/dL
  - `PASI_ORTA_UST = 10.0` (sistemik tedavi eşiği)
  - `DLQI_YUKSEK = 10.0`
- `LABEL_NAMES = ["ftr", "aile_hekimligi", "sistemik_tedavi"]`
- `set_global_seed()` — deterministik çıktı garantisi için

**Dikkat:** `class Config` yapısı Pydantic v2'de deprecate edildi.

```python
# Hatalı (eski):
class Config:
    env_file = ".env"

# Düzeltildi:
model_config = {
    "env_file": ".env",
    "env_file_encoding": "utf-8",
    "case_sensitive": False,
}
```

---

## Adım 5 — feature_store/schema.py

**Amaç:** Tüm hasta özelliklerinin tek bir yerde tanımlandığı merkezi şema.

### v1.0 — Zorunlu alanlar (kural motorundan):

```python
tirnak_tutulumu: bool       # FTR göstergesi
sabah_turuklugu_30dk: bool  # FTR göstergesi (>30 dk)
vki: float                  # kg/m² — AH eşik: >30
ldl: float                  # mg/dL — AH eşik: >130
pasi_skoru: float           # 0–72 — Sistemik eşik: >10
sigara: bool                # AH göstergesi
```

### v2.0 — Opsiyonel alanlar (hocadan gelecek):

```python
dlqi: Optional[float]                      # 0–30, yaşam kalitesi
bsa: Optional[float]                       # % vücut yüzey alanı
psoriazis_tipi: Optional[PsoriasisType]    # Enum: plak/gutat/inverz...
yas: Optional[int]
cinsiyet: Optional[Gender]
hastalik_suresi_ay: Optional[int]
eklem_bulgulari: Optional[bool]
onceki_sistemik_yanit: Optional[SystemicResponse]
```

### Genişletilebilir alan:

```python
extra_features: dict = field(default_factory=dict)
# Şemada olmayan yeni parametreler buraya girer
```

### PatientLabels dataclass:

```python
ftr: bool
aile_hekimligi: bool
sistemik_tedavi: bool

# Yardımcı metodlar:
to_array()               # → [0, 1, 1]
from_array([0, 1, 1])    # → PatientLabels(ftr=False, ...)
```

---

## Adım 6 — preprocessing/feature_engineering.py

**Amaç:** Ham hasta verisi → model özellik vektörü.

### Üretilen 17 özellik (v1.0):

| Özellik | Tür | Açıklama |
|---------|-----|----------|
| tirnak_tutulumu | Binary | Doğrudan |
| sabah_turuklugu | Binary | Doğrudan |
| vki | Sayısal | Doğrudan |
| ldl | Sayısal | Doğrudan |
| pasi_skoru | Sayısal | Doğrudan |
| sigara | Binary | Doğrudan |
| vki_obez | Binary | VKİ > 30 |
| vki_asiri_obez | Binary | VKİ > 35 |
| ldl_yuksek | Binary | LDL > 130 |
| ldl_cok_yuksek | Binary | LDL > 160 |
| pasi_orta | Binary | 5 < PASI ≤ 10 |
| pasi_siddetli | Binary | PASI > 10 |
| kardiyovaskuler_risk | Sayısal 0–3 | obez + yüksek LDL + sigara |
| eklem_risk | Binary | tırnak OR sabah tutukluğu |
| rule_ftr | Binary | Mevcut kural motorunun FTR kararı |
| rule_aile | Binary | Mevcut kural motorunun AH kararı |
| rule_sistemik | Binary | Mevcut kural motorunun Sistemik kararı |

> **Önemli tasarım kararı:** rule_* özellikleri modele feature olarak verilir.
> Bu, modelin kural mantığını öğrenmesini ve üzerine koymasını sağlar.

### Özellik sırası korunur:

```python
V1_FEATURES = ["tirnak_tutulumu", "sabah_turuklugu", ...]
# Bu liste model artifact'larıyla birlikte kaydedilir.
# Değiştirilmez — yeni özellikler SADECE listenin SONUNA eklenir.
```

---

## Adım 7 — preprocessing/pipeline.py

**Amaç:** Scikit-learn benzeri fit()/transform() API.

### Pipeline akışı:

```
PatientFeatures listesi
    → feature_engineering (her hasta için)
    → numpy matrix [n_samples, n_features]
    → StandardScaler (sadece sayısal sütunlar)
    → Hazır X matrisi
```

### Önemli noktalar:
- `fit()` SADECE train split üzerinde çağrılır
- `transform()` train + val + test için
- `transform_single()` inference için tek hasta
- `save()` / `load()` → joblib ile serializasyon
- `save_feature_names()` → feature_names.json (versiyonlama)

---

## Adım 8 — scripts/generate_synthetic_data.py

**Amaç:** Gerçek hasta verisi gelmeden pipeline'ı çalışır hale getirmek.

### Yöntem:
1. Türk popülasyonu istatistiklerine yakın dağılımlarla hasta üret
2. Mevcut kural motorunu ground truth olarak kullan
3. Opsiyonel gürültü ekle (--noise 0.02)

### Hasta dağılımları:

```python
tirnak_tutulumu  ~ Bernoulli(p=0.40)
sabah_turuklugu  ~ Bernoulli(p=0.30)
vki              ~ clip(Normal(28.5, 6.0), 15, 55)
ldl              ~ clip(Normal(118, 32), 40, 280)
pasi_skoru       ~ clip(Exponential(7.5), 0, 72)  # Sağa çarpık
sigara           ~ Bernoulli(p=0.35)
```

### Kullanım:

```bash
python scripts/generate_synthetic_data.py --n 1000 --output data/synthetic/patients.parquet
python scripts/generate_synthetic_data.py --n 1000 --noise 0.0  # Gürültüsüz
```

---

## Adım 9 — models/trainer.py

**Amaç:** Binary Relevance stratejisiyle 3 ayrı XGBoost modeli eğitmek.

### Eğitim akışı:

```
Veri → Split (70/15/15) → Pipeline.fit(train) → transform(tümü)
    → Label başına: Optuna optimize → XGBClassifier.fit()
    → Modelleri kaydet
```

### Sınıf dengesizliği sorunu ve çözümü:

**Sorun:** İlk çalıştırmada Sistemik Tedavi için F1 = 0.0000

```
Sistemik Tedavi  F1: 0.0000   TN=214 FP=0 FN=86 TP=0
```

**Neden?** PASI > 10 az görülen bir durum (%26 pozitif oran).
min_child_weight=5 ile model azınlık sınıfına hiç girmedi.

**Çözüm:** scale_pos_weight otomatik hesaplanması eklendi:

```python
pos_rate = y_tr.mean()
scale_pos_weight = (1 - pos_rate) / pos_rate
# Sistemik için: (0.74 / 0.26) ≈ 2.8
```

**Sonuç:** Sistemik F1: 0.0 → 0.9467 (gürültülü), 1.0000 (gürültüsüz)

### Hiperparametre arama uzayı (Optuna):

```python
max_depth:          [2, 5]
learning_rate:      [0.01, 0.2]  # log-scale
n_estimators:       [100, 500]
subsample:          [0.6, 1.0]
colsample_bytree:   [0.6, 1.0]
min_child_weight:   [1, 10]
alpha (L1):         [0.0, 1.0]
lambda (L2):        [0.5, 3.0]
```

### Model versiyonlama:

```
models/artifacts/
├── v1.0/
│   ├── model_ftr.pkl
│   ├── model_aile_hekimligi.pkl
│   ├── model_sistemik_tedavi.pkl
│   ├── preprocessor.pkl
│   ├── feature_names.json
│   └── metadata.json
└── production → v1.0/  (symlink)
```

---

## Adım 10 — models/evaluator.py

**Amaç:** Multi-label performans metrikleri.

### Hesaplanan metrikler:

**Per-label:** F1, Precision, Recall, AUC-ROC, Confusion Matrix

**Overall:** Exact Match Accuracy, Hamming Loss, Macro F1, Micro F1

### Hedef kontrolü:

```python
check_target_achieved(report, target_f1=0.98)
# ✅ veya hangi label'ların geride kaldığını gösterir
```

---

## Adım 11 — models/predictor.py

**Amaç:** Kaydedilmiş modelleri yükleyip inference yapmak.

### Önemli tasarım kararları:
- `Predictor.load("models/artifacts/production")` → symlink üzerinden güncel model
- `Predictor.load_safe()` → model yoksa crash değil, None döner
- Per-label eşik (threshold) desteklenir — klinik önceliğe göre ayarlanabilir
- `PredictionResult.to_dict()` → JSON serialize edilebilir çıktı

---

## Adım 12 — explainability/shap_explainer.py

**Amaç:** Her karar için "Neden?" sorusunu yanıtlamak.

### SHAP türü: TreeExplainer
- XGBoost için native, hızlı
- Her label için ayrı explainer (Binary Relevance'a uygun)

### Çıktı formatı (doktora gösterilecek):

```json
{
  "ftr": {
    "label_adi": "Fizik Tedavi ve Rehabilitasyon (FTR)",
    "top_faktorler": [
      {
        "ozellik": "Tırnak tutulumu",
        "shap_degeri": 0.42,
        "etki": "+0.420 (karar yönünde)"
      }
    ]
  }
}
```

### Görselleştirme:
- `plot_waterfall()` — tek hasta için karar ağacı
- `plot_summary()` — tüm test seti için global özellik önemi

---

## Adım 13 — llm/explainer.py

**Amaç:** ML kararını doktor dostu Türkçe'ye çevirmek.

### Kritik sınır:

```
LLM → Karar AÇIKLAR          ✅
LLM → Karar VERİR            ❌ (asla)
LLM → Karar DEĞİŞTİRİR       ❌ (asla)
```

### System prompt tasarımı:
- Sadece verilen verilere dayan
- Modelin kararını asla değiştirme
- "Sistem şunu öneriyor:" ile başla
- Maks. 200 kelime
- Faktörleri önem sırasına göre sun

### Fallback mekanizması:
API key yoksa veya Gemini erişilemezse otomatik şablon kullanılır.
Sistem asla crash etmez.

---

## Adım 14 — audit/logger.py

**Amaç:** Her tahmin kararını tam izlenebilirlik için kayıt altına almak.

### Kayıt edilen veriler:

```
timestamp, hasta_id, model_version
input_json              → tam hasta giriş verisi
pred_ftr/aile/sistemik  → binary kararlar
prob_ftr/aile/sistemik  → olasılık skorları
shap_json               → SHAP değerleri
llm_explanation         → LLM açıklama metni
processing_time_ms
```

### Neden audit log kritik?
- Tıbbi kullanımda her karar izlenebilir olmalı
- "Bu karar neden verildi?" sorusu sonradan da yanıtlanabilmeli
- Üretimde KVKK uyumluluğu için zorunlu

---

## Adım 15 — api/main.py

**Amaç:** Tüm servisleri birleştiren REST API.

### Endpoint'ler:

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | /predict | Tahmin + SHAP + LLM açıklaması |
| GET | /health | Model yüklü mü? LLM aktif mi? |
| GET | /audit/logs | Son tahmin kayıtları |
| GET | /docs | Otomatik API dokümantasyonu |

### /predict akışı:

```
PatientInput (Pydantic validasyon)
    → PatientFeatures oluştur
    → pipeline.transform_single()
    → [3x] model.predict_proba()
    → shap_explainer.explain_single()
    → llm_explainer.explain()
    → audit_logger.log()
    → PredictionResponse (JSON)
```

---

## Adım 16 — tests/test_pipeline.py

### Test grupları ve sayıları:

| Grup | Test Sayısı |
|------|-------------|
| TestRuleEngine | 7 |
| TestFeatureEngineering | 5 |
| TestPreprocessingPipeline | 5 |
| TestPatientFeaturesValidation | 4 |
| TestSyntheticData | 3 |
| **Toplam** | **24** |

### Sonuç:

```
======================= 24 passed, 2 warnings in 29.42s ========================
```

### 2 uyarı ve çözümleri:
1. `PytestConfigWarning: Unknown config option: asyncio_mode`
   → pytest-asyncio kurulmamış, async test yok, zararsız
2. `PydanticDeprecatedSince20: Support for class-based config is deprecated`
   → settings.py'de `class Config` → `model_config = {}` olarak düzeltildi ✅

---

## Adım 17 — Bağımlılık Kurulumu

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install numpy pandas scikit-learn xgboost shap pydantic pydantic-settings \
    joblib optuna fastapi "uvicorn[standard]" sqlalchemy loguru \
    matplotlib seaborn pyarrow python-dotenv pytest pytest-cov httpx
```

### Sorun: iterstrat paketi Python 3.13'te yok

**Çözüm:** try/except ImportError ile sklearn fallback eklendi:

```python
try:
    from iterstrat.ml_stratifiers import MultilabelStratifiedShuffleSplit
    # iterstrat ile stratified split
except ImportError:
    # sklearn ShuffleSplit ile fallback
```

---

## Adım 18 — Model Eğitimi Deneyleri

### Deney 1: İlk çalıştırma (no-optimize, noise=0.02)

```
FTR           F1: 0.9867   ✅
Aile Hek.     F1: 0.9827   ✅
Sistemik      F1: 0.0000   ⚠️  ← Sorun! Class imbalance
```

### Deney 2: scale_pos_weight düzeltmesi

```
FTR           F1: 0.9867   ✅
Aile Hek.     F1: 0.9827   ✅
Sistemik      F1: 0.9467   ⚠️  ← Büyük iyileşme (0→0.94)
```

### Deney 3: Optuna (80 trial, n=3000, noise=0.02)

```
FTR           F1: 0.9777   ⚠️
Aile Hek.     F1: 0.9807   ✅
Sistemik      F1: 0.9437   ⚠️
```

Not: %2 gürültü F1 tavanını ~0.97–0.98 ile sınırlıyor.

### Deney 4: Gürültüsüz veri (no-optimize, noise=0.0, n=3000)

```
FTR           F1: 1.0000   ✅
Aile Hek.     F1: 1.0000   ✅
Sistemik      F1: 1.0000   ✅
Exact Match:  1.0000
Hamming Loss: 0.0000
```

Yorum: Mimari doğru. Model kural motorunu mükemmel öğreniyor.
Gürültülü versiyondaki düşüş, gerçek hasta verilerindeki klinisyen yargı
farklılıklarını simüle ediyor — bu beklenen davranış.

---

## Öğrenilen Dersler

1. **scale_pos_weight zorunlu** — Azınlık sınıfı (Sistemik) için otomatik hesaplanmalı
2. **Pydantic v2'de class Config deprecated** — model_config = {} kullan
3. **iterstrat Python 3.13'te yok** — Her zaman sklearn fallback yaz
4. **Gürültü F1 tavanını belirler** — noise=0.02 ile teorik maksimum ~0.98
5. **Kural özelliklerini feature olarak ekle** — rule_ftr, rule_aile, rule_sistemik modelin
   öğrenmesini dramatik biçimde hızlandırıyor
6. **Test seti kilitlenmeli** — Optuna sadece val seti üzerinde çalışmalı

---

## Üretilen Dosyalar (19 adet)

```
dermatology_project/
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── steps.md                              ← Bu dosya
├── config/
│   └── settings.py
├── feature_store/
│   └── schema.py
├── preprocessing/
│   ├── feature_engineering.py
│   └── pipeline.py
├── models/
│   ├── trainer.py
│   ├── evaluator.py
│   ├── predictor.py
│   └── artifacts/v1.0/                  ← Eğitilmiş modeller (git'e girmiyor)
│       ├── model_ftr.pkl
│       ├── model_aile_hekimligi.pkl
│       ├── model_sistemik_tedavi.pkl
│       ├── preprocessor.pkl
│       ├── feature_names.json
│       └── metadata.json
├── explainability/
│   └── shap_explainer.py
├── llm/
│   └── explainer.py
├── api/
│   └── main.py
├── audit/
│   └── logger.py
├── scripts/
│   ├── generate_synthetic_data.py
│   └── train_model.py
└── tests/
    └── test_pipeline.py                  ← 24/24 test ✅
```

---

## Sıradaki Adımlar (Faz 1 Kalan)

- [x] API uçtan uca entegrasyon testi (FastAPI TestClient)
- [x] `.env` dosyası oluştur, API'yi başlat: `uvicorn api.main:app --reload`
- [x] http://localhost:8000/docs üzerinden manuel test
- [ ] SHAP waterfall plot çıktısını doğrula

---

---

# Faz 2 — .NET Blazor Web Arayüzü

> **Tarih**: 29–30 Temmuz 2026  
> **Amaç**: Doktorların kullanacağı klinik arayüzü .NET 8 Blazor Server ile geliştirmek  
> **Platform**: ASP.NET Core 8 Blazor Web App (Interactive Server rendering)  
> **URL**: http://localhost:5000  
> **FastAPI Backend**: http://localhost:8000

---

## Adım 1 — Teknoloji Kararı

| Karar | Seçim | Gerekçe |
|-------|-------|---------|
| Web framework | ASP.NET Core 8 Blazor Server | Klinik ortamda C# yetkinliği, real-time SignalR bağlantısı |
| Render modu | Interactive Server | WASM gerektirmiyor; sunucu tarafı state yönetimi yeterli |
| CSS | Vanilla CSS (custom design system) | Bootstrap kaldırıldı; tam kontrol, premium dark UI |
| Font | Inter (Google Fonts) | Modern, okunabilir, klinik ortama uygun |
| HTTP auth | Bearer token (appsettings.json'dan) | Faz 3'te AD/JWT ile değiştirilecek placeholder |

---

## Adım 2 — Proje İskeleti Oluşturma

```bash
dotnet new blazor -n cdss_web --interactivity Server --no-restore
mkdir -p cdss_web/Models cdss_web/Services
```

> **Not:** `.NET 8`'de `blazorserver` şablonu artık mevcut değil.
> Yeni şablon adı `blazor` + `--interactivity Server` bayrağı.

Oluşturulan scaffold yapısı:
```
cdss_web/
├── Components/
│   ├── App.razor
│   ├── Routes.razor
│   ├── _Imports.razor
│   ├── Layout/
│   │   ├── MainLayout.razor
│   │   └── NavMenu.razor
│   └── Pages/
│       ├── Counter.razor   ← silindi
│       ├── Weather.razor   ← silindi
│       ├── Home.razor
│       └── Error.razor
├── Program.cs
├── appsettings.json
└── wwwroot/
```

Gereksiz scaffold sayfaları silindi:
```bash
rm cdss_web/Components/Pages/Counter.razor
rm cdss_web/Components/Pages/Weather.razor
```

---

## Adım 3 — appsettings.json (Token Auth)

```json
{
  "ApiSettings": {
    "BaseUrl": "http://127.0.0.1:8000",
    "TestToken": "cdss-dev-token-2024"
  }
}
```

**Tasarım kararı:** `localhost` yerine `127.0.0.1` kullanıldı.
Neden: macOS'ta .NET'in `HttpClient`'ı `localhost`'u IPv6 (`::1`) olarak çözümleyebilir,
ancak FastAPI yalnızca IPv4 `0.0.0.0` üzerinden dinler — bu bağlantı hatasına yol açar.

**Auth yaklaşımı:**
- Şu an: `appsettings.json`'daki sabit token her HTTP isteğine `Authorization: Bearer <token>` olarak ekleniyor
- Faz 3: Hastane AD (Active Directory) veya gerçek JWT entegrasyonu yapılacak

---

## Adım 4 — Program.cs (DI Kaydı)

```csharp
builder.Services.AddHttpClient<CdssApiService>(client =>
{
    var apiSettings = builder.Configuration.GetSection("ApiSettings");
    client.BaseAddress = new Uri(apiSettings["BaseUrl"] ?? "http://127.0.0.1:8000");
    client.Timeout = TimeSpan.FromSeconds(30);
});
```

**Kritik hata ve çözümü:**

İlk sürümde `AddHttpClient<>` kaydının hemen ardından yanlışlıkla `AddScoped<CdssApiService>()` de çağrıldı.

Sorun: `AddScoped` önceki `AddHttpClient` kaydını ezer; yeni DI çözümlemesi `BaseAddress` yapılandırılmamış boş bir `HttpClient` enjekte eder.

```
[Health Check Error] An invalid request URI was provided.
Either the request URI must be an absolute URI or BaseAddress must be set.
```

**Çözüm:** `AddScoped<CdssApiService>()` satırı silindi. `AddHttpClient<T>` zaten
typed client'ı scoped olarak kaydeder — ikinci kayıt gereksiz ve zararlı.

---

## Adım 5 — Models/PatientInputModel.cs

Blazor `EditForm` için giriş modeli. `DataAnnotations` ile anlık validasyon.

```csharp
public class PatientInputModel
{
    [Required] public string HastaId { get; set; }

    // v1.0 binary
    public bool TirnakTutulumu { get; set; }
    public bool SabahTuruklugu30dk { get; set; }
    public bool Sigara { get; set; }

    // v1.0 sayısal
    [Range(0.0, 72.0)] public double PasiSkoru { get; set; }
    [Range(10.0, 80.0)] public double Vki { get; set; }
    [Range(0.0, 500.0)] public double Ldl { get; set; }

    // v2.0 opsiyonel (null bırakılabilir)
    public double? Dlqi { get; set; }
    public double? Bsa { get; set; }
    public int? Yas { get; set; }

    // FastAPI snake_case payload'ına dönüştürme
    public Dictionary<string, object?> ToApiPayload() => new() { ... };
}
```

---

## Adım 6 — Models/PredictionResponse.cs

FastAPI yanıtlarını strongly-typed C# record'larına eşleyen dosya.
`JsonPropertyName` attribute'ları ile snake_case → PascalCase dönüşümü yapılır.

```csharp
public record HealthResponse(
    [property: JsonPropertyName("model_yuklendi")]  bool ModelYuklendi,
    [property: JsonPropertyName("model_versiyonu")] string? ModelVersiyonu,
    [property: JsonPropertyName("llm_aktif")]       bool LlmAktif,
    ...
);

public record PredictionResponse(
    [property: JsonPropertyName("tahmin")]            Dictionary<string, LabelDetail> Tahmin,
    [property: JsonPropertyName("shap_aciklamalari")] Dictionary<string, ShapExplanation> ShapAciklamalari,
    [property: JsonPropertyName("llm_aciklamasi")]    string LlmAciklamasi,
    [property: JsonPropertyName("audit_id")]          int AuditId,
    ...
);
```

UI yardımcı sınıfı `LabelCardModel` — SHAP çubuğu genişliğini hesaplar:

```csharp
public int ShapBarWidth(ShapFactor f) =>
    MaxAbsShap > 0 ? (int)(Math.Abs(f.ShapDegeri) / MaxAbsShap * 100) : 0;
```

---

## Adım 7 — Services/CdssApiService.cs

Her HTTP isteğine Bearer token ekleyen servis.

```csharp
private HttpRequestMessage CreateRequest(HttpMethod method, string endpoint)
{
    var request = new HttpRequestMessage(method, endpoint);
    request.Headers.Authorization =
        new AuthenticationHeaderValue("Bearer", _testToken);
    return request;
}
```

Endpoint'ler:
| Metod | Endpoint | Açıklama |
|-------|----------|----------|
| `PredictAsync(patient)` | `POST /predict` | Tahmin + SHAP + LLM |
| `GetHealthAsync()` | `GET /health` | API ve model durumu |
| `GetLogsAsync(limit, hastaId)` | `GET /audit/logs` | Geçmiş kararlar |

Hata yönetimi:
- `HttpRequestException` → bağlantı hatası mesajı (Türkçe)
- `TaskCanceledException` → zaman aşımı mesajı
- `!IsSuccessStatusCode` → HTTP hata kodu + body

---

## Adım 8 — wwwroot/app.css (Design System)

Bootstrap tamamen kaldırıldı. Özel CSS design sistemi oluşturuldu.

### Renk paleti (CSS değişkenleri):

```css
--bg-primary:     #0B1120;   /* Koyu lacivert arka plan */
--bg-secondary:   #111827;   /* Sidebar */
--bg-card:        #1E2D3D;   /* Kart arka planı */
--accent:         #14B8A6;   /* Teal — ana vurgu rengi */
--success:        #22C55E;   /* Yeşil — pozitif karar */
--danger:         #EF4444;   /* Kırmızı — hata */
--warning:        #F59E0B;   /* Amber — Sistemik Tedavi */
```

### Özel bileşenler:

| Bileşen | Açıklama |
|---------|----------|
| `.sidebar` | Fixed 240px sol panel, API durum göstergesi |
| `.toggle-row` | Klinik bulgular için özel checkbox switcher |
| `.result-card` | Pozitif/negatif karar kartları (gradyan arka plan) |
| `.prob-bar-fill` | Animasyonlu olasılık barı |
| `.shap-bar-fill` | SHAP etkisi barı (teal=pozitif, kırmızı=negatif) |
| `.llm-box` | Sol kenarda teal çizgi ile LLM açıklama kutusu |
| `.data-table` | Geçmiş kararlar tablosu |
| `.label-chip` | FTR/Aile/Sistemik renkli etiket |

### Animasyonlar:
```css
@keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
/* Sonuç kartları 0.4s, LLM kutusu 0.3s gecikmeyle girer */
```

---

## Adım 9 — Components/App.razor

Bootstrap CSS kaldırıldı. Google Fonts Inter eklendi. Dil `tr` yapıldı.

```html
<html lang="tr">
<head>
    <link href="https://fonts.googleapis.com/css2?family=Inter:..." rel="stylesheet" />
    <link rel="stylesheet" href="app.css" />
    <!-- bootstrap/bootstrap.min.css KALDIRILDI -->
</head>
```

---

## Adım 10 — Components/_Imports.razor

Tüm Razor component'larına global namespace açıldı:

```razor
@using cdss_web.Components.Layout
@using cdss_web.Models
@using cdss_web.Services
```

**Build hatası ve çözümü:**

İlk build denemesinde `CdssApiService`, `HealthResponse`, `MainLayout` gibi tipler
her component dosyasında `@using` direktifi gerektiriyordu.
`_Imports.razor`'a eklenmesiyle tüm component'larda otomatik kullanılabilir hale geldi.

---

## Adım 11 — Components/Layout/MainLayout.razor

Sidebar içeren ana layout. `OnInitializedAsync`'te API health check yapar.

```razor
<div class="sidebar-footer">
    <span class="status-dot @(_apiOnline ? "online" : "offline")"></span>
    <span>@(_apiOnline ? "API Bağlı" : "API Bağlanamıyor")</span>
</div>

@code {
    protected override async Task OnInitializedAsync()
    {
        var health = await ApiService.GetHealthAsync();
        _apiOnline = health?.ModelYuklendi ?? false;
        _modelVersion = health?.ModelVersiyonu;
    }
}
```

NavMenu.razor scaffold boşaltıldı; navigasyon doğrudan MainLayout'ta inline yazıldı.

---

## Adım 12 — Components/Pages/Home.razor

Anasayfa: sistem durumu kartları, nasıl kullanılır rehberi, birim açıklamaları.

```
┌──────────────────────────────────────────────────────┐
│  Psoriazis Karar Destek Sistemi                      │
│  "Makine öğrenmesi destekli klinik karar sistemi…"   │
├───────────────┬───────────────┬──────────────────────┤
│ v1.0          │ Pasif         │ Bağlı ✅             │
│ Aktif Model   │ LLM Motoru    │ API Durumu           │
└───────────────┴───────────────┴──────────────────────┘
```

---

## Adım 13 — Components/Pages/Predict.razor

Ana değerlendirme sayfası. İki moddan oluşur: form görünümü ve sonuç görünümü.

### Form görünümü:

```
Hasta ID
Klinik Bulgular (3x toggle switch)
  ├── Tırnak Tutulumu
  ├── Sabah Tutukluğu >30dk
  └── Sigara
Ölçüm Değerleri (3 zorunlu + 3 opsiyonel)
  ├── PASI Skoru     → hint: "7.5 — Orta şiddetli"
  ├── VKİ            → hint: "33.5 — Obez (eşik: >30)"
  ├── LDL            → hint: "148 mg/dL — Yüksek (eşik: >130)"
  ├── DLQI           (opsiyonel, v2.0)
  ├── BSA %          (opsiyonel, v2.0)
  └── Yaş            (opsiyonel, v2.0)
[Değerlendir] [Temizle]
```

### Sonuç görünümü (3 kart):

```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ 🏃 ÖNERİLİYOR   │ │ 🏥 ÖNERİLİYOR   │ │ 💊 ÖNERİLİYOR   │
│ FTR              │ │ Aile Hekimliği   │ │ Sistemik Tedavi  │
│ ████████████ %52 │ │ ████████████ %52 │ │ ████████████ %52 │
│ Etkili Faktörler │ │ Etkili Faktörler │ │ Etkili Faktörler │
│ ▲ rule_ftr 0.099 │ │ ▲ kardio  0.098  │ │ ▲ pasi    0.101  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
💬 Klinik Açıklama (LLM) — Gemini Flash
```

**Razor parser hatası ve çözümü:**

`switch` expression içinde `<` operatörü Razor parser'ı bozuyordu:

```csharp
// HATALI — Razor < operatörünü HTML tag zannetti:
v switch { < 10 => "Zayıf", ... }

// DOĞRU — if/else ile yeniden yazıldı:
if (v < 10) return "Zayıf";
```

---

## Adım 14 — Components/Pages/AuditLog.razor

Geçmiş kararlar tablosu. Hasta ID'ye göre filtreleme desteklenir.

| # | Tarih/Saat | Hasta ID | Önerilen Birimler | Süre | Model |
|---|-----------|----------|-------------------|------|-------|
| 3 | 30.07.2026 13:04 | PSO-TEST-001 | 🏃 FTR 🏥 Aile Hek. 💊 Sistemik | 7 ms | v1.0 |

---

## Adım 15 — Build ve Doğrulama

### Build sonucu:
```bash
cd cdss_web && dotnet build
# ✅ 0 Hata, 0 Uyarı
```

### Uçtan uca test (`PSO-TEST-001`):
```bash
curl -X POST http://localhost:8000/predict \
  -d '{"hasta_id":"PSO-TEST-001","tirnak_tutulumu":true,
       "sabah_turuklugu_30dk":true,"vki":33.5,
       "ldl":148.0,"pasi_skoru":12.5,"sigara":true}'
```

**Sonuç:**
```json
{
  "aktif_birimler": ["FTR", "Aile Hekimliği", "Sistemik Tedavi"],
  "shap_aciklamalari": {
    "ftr":             { "top_faktor": "rule_ftr (+0.099)" },
    "aile_hekimligi":  { "top_faktor": "kardiyovaskuler_risk (+0.098)" },
    "sistemik_tedavi": { "top_faktor": "pasi_skoru (+0.101)" }
  },
  "islem_suresi_ms": 7.5,
  "audit_id": 3
}
```

---

## Öğrenilen Dersler (Faz 2)

1. **AddHttpClient + AddScoped çakışması** — `AddHttpClient<T>` typed client'ı zaten scoped olarak kaydeder; ayrıca `AddScoped<T>()` çağrısı BaseAddress yapılandırmasını ezer.

2. **localhost vs 127.0.0.1** — macOS'ta .NET `HttpClient` `localhost`'u IPv6 olarak çözümleyebilir; FastAPI yalnızca IPv4'te dinliyorsa bağlantı sessizce başarısız olur. `127.0.0.1` kullan.

3. **Razor'da `<` operatörü** — `@code` bloğunda `switch` expression veya karşılaştırmalarda `<` operatörü kullanılırsa Razor parser bunu HTML tag olarak yanlış yorumlayabilir. `if/else` ile rewrite et.

4. **_Imports.razor zorunlu** — Servis ve model namespace'leri `_Imports.razor`'a eklenmeden her component'ta tek tek `@using` yazmak gerekir; bu hata kaynağıdır.

5. **Bootstrap kaldır** — Blazor scaffold'u Bootstrap ile gelir; özel bir design sistemi istiyorsan `App.razor`'dan `bootstrap.min.css` linkini sil, yoksa iki CSS sistemi çakışır.

---

## Üretilen Dosyalar (Faz 2 — 12 adet)

```
cdss_web/
├── appsettings.json                ← API URL + TestToken
├── Program.cs                      ← DI kaydı (AddHttpClient)
├── Models/
│   ├── PatientInputModel.cs        ← Form modeli + validasyon
│   └── PredictionResponse.cs       ← API yanıt record'ları + LabelCardModel
├── Services/
│   └── CdssApiService.cs           ← Bearer token ile HTTP servis
├── Components/
│   ├── App.razor                   ← Bootstrap kaldırıldı, Inter font eklendi
│   ├── Routes.razor                ← Türkçe 404 sayfası
│   ├── _Imports.razor              ← Global namespace'ler
│   ├── Layout/
│   │   └── MainLayout.razor        ← Sidebar + canlı API durum göstergesi
│   └── Pages/
│       ├── Home.razor              ← Anasayfa (sistem durumu + rehber)
│       ├── Predict.razor           ← Hasta formu + sonuç kartları + SHAP
│       └── AuditLog.razor          ← Geçmiş kararlar tablosu
└── wwwroot/
    └── app.css                     ← Özel dark medical UI (~500 satır CSS)
```

---

## Çalıştırma Komutları

```bash
# Terminal 1 — FastAPI Backend
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Blazor Web Arayüzü
cd cdss_web && dotnet run --urls "http://localhost:5000"
```

| Sayfa | URL |
|-------|-----|
| 🏠 Anasayfa | http://localhost:5000 |
| 🔬 Hasta Değerlendirme | http://localhost:5000/degerlendirme |
| 📋 Geçmiş Kararlar | http://localhost:5000/gecmis |
| 📖 FastAPI Docs | http://localhost:8000/docs |

---

## Sıradaki Adımlar (Faz 3)

- [ ] Gerçek hasta verisi ETL pipeline'ı
- [ ] Hastane veri formatına özel parser
- [ ] Retrospektif validasyon (eski doktor kararları vs. model)
- [ ] Model v2.0 eğitimi (gerçek veriyle)
- [ ] Kimlik doğrulama — Hastane AD / JWT login sayfası
- [ ] KVKK uyumluluk katmanı (veri maskeleme, log şifreleme)
- [ ] PDF rapor çıktısı (doktor kararı yazdırma)
- [ ] İzleme / alerting (Sentry veya Azure Monitor)

---

# Faz 3 — Adım Adım Uygulama Kaydı

> **Tarih**: 14 Ağustos 2026  
> **Amaç**: Güvenlik, Raporlama ve Web Arayüzü Geliştirmeleri  
> **Ortam**: Blazor Server (.NET 8), C#, macOS  

---

## Adım 1 — Kimlik Doğrulama ve Login Ekranı (Authentication)

**Amaç:** Açık sistemin güvenliğini sağlamak.

### 1.1 CustomAuthStateProvider.cs
Blazor Server için özel bir kimlik doğrulayıcı yazıldı.
- `ProtectedSessionStorage` ile tarayıcıda şifreli oturum yönetimi sağlandı.
- Şimdilik hardcoded hesaplar: `doktor` (`cdss2024`) ve `admin` (`admin2024`).

### 1.2 Login.razor
- Koyu tema (Dark Mode) uyumlu giriş sayfası yapıldı.
- Başarısız giriş denemeleri için UI hata mesajları eklendi.

### 1.3 Routing Güvenliği
- `MainLayout.razor` içerisinde `OnAfterRenderAsync` kullanarak oturum kontrolü yapıldı.
- Giriş yapmamış kullanıcılar otomatik olarak `/login` adresine yönlendirildi.

---

## Adım 2 — Oturum Zaman Aşımı (Session Timeout)

**Amaç:** Doktorun masadan ayrılması durumunda 30 dakikalık inactivity sonrası oturumu sonlandırmak.

### 2.1 JavaScript Aktivite Takibi
- `cdss.js` oluşturularak fare hareketi, klavye ve tıklama gibi olaylar (`mousemove`, `keydown`) dinlendi.
- Boşta geçen süreyi dönen `getIdleSeconds` fonksiyonu yazıldı.

### 2.2 Arka Plan Zamanlayıcı (Timer)
- `MainLayout.razor` içinde her 30 saniyede bir çalışan `System.Timers.Timer` eklendi.
- **Kritik Çözüm:** Timer arka plan thread'inde çalıştığı için JS interop hata veriyordu. Timer eventi `InvokeAsync(TimeoutKontrol)` içine alınarak UI Thread'e senkronize edildi.

### 2.3 UI Uyarıları
- Son 60 saniye kala kullanıcıya "Oturumunuz kapanıyor, devam et?" pop-up'ı gösterildi.

---

## Adım 3 — PDF Karar Raporu İndirme

**Amaç:** Modelin kararlarını HBYS'ye eklenmek üzere resmi bir formata dökmek.

### 3.1 QuestPDF Entegrasyonu
- `QuestPDF` kütüphanesi projeye eklendi (`dotnet add package QuestPDF`).
- Font lisansı için `QuestPDF.Settings.License = LicenseType.Community` ayarı yapıldı.

### 3.2 PdfReportService.cs
- `Document.Create` yapısıyla klinik rapor şablonu oluşturuldu.
- Hastanın parametreleri (PASI, VKİ vb.), önerilen kararlar, SHAP tabanlı yapay zeka açıklaması tek bir dosyada birleştirildi.
- Negatif kararların güven skoru düzeltildi: Olasılık (`p`) düşükse, güven `= 1 - p` şeklinde rapora eklendi.

### 3.3 İndirme Tetikleyicisi
- `cdss.js` içine `downloadFile(filename, base64)` fonksiyonu yazıldı.
- `Predict.razor` içine "📄 Raporu İndir" butonu eklenip JS ile köprü kuruldu.

---

## Adım 4 — KVKK Uyumlu Audit Log UI

**Amaç:** Verilen tüm kararların geriye dönük izlenebilmesi (Sadece Admin yetkisiyle).

### 4.1 AuditLogs.razor
- Sisteme `/audit-log` sayfası eklendi.
- `CdssApiService.cs` içindeki `GetLogsAsync` metoduna bağlandı.

### 4.2 KVKK Veri Maskeleme
- Tablo üzerinde gösterilen hasta ID'leri `Ha****12` formatına sokularak hasta mahremiyeti korundu.

---

## Adım 5 — Blazor SSR ve UI İyileştirmeleri

**Amaç:** Arayüzün kullanım kolaylığı ve butonların stabil çalışması.

### 5.1 InteractiveServer Problemi
- Blazor .NET 8 varsayılan olarak "Static Server Rendering" (SSR) kullandığı için `MainLayout.razor` içindeki buton tıklamaları (`@onclick`) algılanmıyordu.
- **Çözüm:** `App.razor` dosyasındaki `Routes` bileşeni `<Routes @rendermode="InteractiveServer" />` olarak güncellendi.
- Bu sayede uygulamanın tüm layout'u ve sayfaları interaktif hale getirildi.

### 5.2 Responsive Sidebar
- Menü öğeleri arttığında "Çıkış Yap" ve "API Durumu" gibi alt bilgi ekranının taşmasını engellemek için `flex-grow: 1` ve `overflow-y: auto` CSS düzeltmeleri yapıldı.

---

## Faz 4 (Prodüksiyon) Bekleyen Adımlar

- [ ] Gerçek hasta verisi ETL pipeline'ı ve Model v2.0 eğitimi
- [ ] Kimlik doğrulama — Hastane AD / JWT login entegrasyonu
- [ ] KVKK uyumluluk katmanı (SQLite veritabanı şifreleme)
- [ ] API Rate limiting ve HTTPS zorunluluğu

# Faz 3 — Adım Adım Uygulama Kaydı

> **Tarih**: 30–31 Temmuz 2026
> **Amaç**: CDSS'i açık prototipten klinik kullanıma uygun, güvenli ve raporlanabilir bir uygulamaya dönüştürmek
> **Ortam**: .NET 8 Blazor Server, macOS, proje dizini: `~/Projects/dermatology_project/cdss_web`
> **Bağımlılıklar**: QuestPDF 2024.x, Microsoft.AspNetCore.Components.Server

---

## Adım 1 — Faz 3 Mimari Kararı

Faz 2'de tüm sayfalar kimlik doğrulama olmadan erişilebilirdi. Faz 3'ün önceliği sistemi klinik güvenlik standartlarına taşımak.

| Karar | Seçim | Gerekçe |
|-------|-------|---------|
| Auth mekanizması | CustomAuthStateProvider | Blazor Server'ın yerleşik `AuthenticationStateProvider` soyutlamasına uyum |
| Oturum saklama | ProtectedSessionStorage | Sunucu taraflı şifreli depolama — tarayıcıda düz metin token yok |
| Rol modeli | Statik rol tanımları (doktor/admin) | Faz 4'te AD/LDAP entegrasyonu yapılacak; şimdilik hızlı prototip |
| Rota güvenliği | `<AuthorizeRouteView>` + `RedirectToLogin` | Blazor'un native auth pipeline'ı, ekstra middleware gereksiz |
| PDF motoru | QuestPDF (Community) | .NET native, kod tabanlı şablon, harici font bağımlılığı yok |
| Session timeout | JS Interop + System.Timers.Timer | JS aktivite olayları → C# timer → Blazor state güncellemesi |
| KVKK maskeleme | Sunucu taraflı string transform | Maskeleme UI'da değil, serviste yapılır — client asla ham ID görmez |

---

## Adım 2 — Paket Kurulumu

```bash
cd cdss_web

# QuestPDF — PDF üretimi için
dotnet add package QuestPDF

# Microsoft.AspNetCore.Components.Authorization — AuthorizeView için
dotnet add package Microsoft.AspNetCore.Components.Authorization
```

### Eklenen referanslar (`_Imports.razor`):

```razor
@using Microsoft.AspNetCore.Components.Authorization
@using Microsoft.AspNetCore.Components.Server.ProtectedBrowserStorage
```

### Program.cs'e eklenen servisler:

```csharp
// Authentication state
builder.Services.AddAuthorizationCore();
builder.Services.AddCascadingAuthenticationState();
builder.Services.AddScoped<AuthenticationStateProvider, CustomAuthStateProvider>();

// PDF servisi
builder.Services.AddScoped<PdfReportService>();

// QuestPDF lisans tanımı (Community — ücretsiz, ticari kullanım için ek onay gerekir)
QuestPDF.Settings.License = LicenseType.Community;
```

---

## Adım 3 — Services/AuthService.cs (Kimlik Doğrulama Çekirdeği)

**Amaç:** Kullanıcı kimlik bilgilerini doğrulamak ve oturum token'ı üretmek.

### Rol ve kullanıcı tanımları:

```csharp
private static readonly Dictionary<string, (string PasswordHash, string Role)> _users = new()
{
    ["doktor"] = (Hash("cdss2024"), "doktor"),
    ["admin"]  = (Hash("admin2024"), "admin"),
};
```

> **Güvenlik notu:** Şifreler düz metin değil, SHA-256 ile hash'lenerek saklanır.
> Faz 4'te LDAP/AD entegrasyonu bu sözlüğün yerini alacak.

### Token üretimi:

```csharp
public string? Authenticate(string username, string password)
{
    if (!_users.TryGetValue(username, out var entry)) return null;
    if (entry.PasswordHash != Hash(password)) return null;

    // Basit kompozit token: "username|role|timestamp"
    // Faz 4'te JWT ile değiştirilecek
    return Convert.ToBase64String(
        Encoding.UTF8.GetBytes($"{username}|{entry.Role}|{DateTime.UtcNow.Ticks}")
    );
}
```

**Tasarım kararı:** Token'a `DateTime.UtcNow.Ticks` eklenmesi, aynı kullanıcının iki farklı oturumunun birbiriyle karışmamasını engeller.

---

## Adım 4 — Services/CustomAuthStateProvider.cs

**Amaç:** Blazor'un `AuthenticationStateProvider` soyutlamasını implemente etmek.

### `ProtectedSessionStorage` kullanımı:

```csharp
private const string StorageKey = "cdss_auth_token";

public override async Task<AuthenticationState> GetAuthenticationStateAsync()
{
    try
    {
        var result = await _storage.GetAsync<string>(StorageKey);
        if (!result.Success || string.IsNullOrEmpty(result.Value))
            return _anonymous;

        var claims = ParseToken(result.Value);
        if (claims is null) return _anonymous;

        var identity = new ClaimsIdentity(claims, "cdss_auth");
        var principal = new ClaimsPrincipal(identity);
        return new AuthenticationState(principal);
    }
    catch
    {
        // Prerender fazında storage erişimi başarısız olabilir — anonymous dön
        return _anonymous;
    }
}
```

**Kritik nokta:** Blazor Server'da prerendering sırasında (bileşen ilk SSR edilirken) `ProtectedSessionStorage`'a erişim `InvalidOperationException` fırlatır. `try/catch` ile yakalanıp `_anonymous` döndürülmesi, sayfanın çökmemesini sağlar; SignalR bağlantısı kurulduktan sonra doğru state otomatik re-render edilir.

### Oturum açma / kapama:

```csharp
public async Task LoginAsync(string token, string username, string role)
{
    await _storage.SetAsync(StorageKey, token);
    var claims = new[] {
        new Claim(ClaimTypes.Name, username),
        new Claim(ClaimTypes.Role, role),
    };
    var principal = new ClaimsPrincipal(new ClaimsIdentity(claims, "cdss_auth"));
    NotifyAuthenticationStateChanged(Task.FromResult(new AuthenticationState(principal)));
}

public async Task LogoutAsync()
{
    await _storage.DeleteAsync(StorageKey);
    NotifyAuthenticationStateChanged(Task.FromResult(_anonymous));
}
```

---

## Adım 5 — Components/Pages/Login.razor

**Amaç:** Dark mode temasına uygun, hata gösterimli giriş ekranı.

### Sayfa yapısı:

```
┌────────────────────────────────────────┐
│          🏥 CDSS                       │
│  Psoriazis Karar Destek Sistemi        │
│                                        │
│  Kullanıcı Adı: [____________]         │
│  Şifre:        [____________]          │
│                                        │
│  ⚠ Kullanıcı adı veya şifre hatalı.   │  ← sadece hata durumunda görünür
│                                        │
│         [  Giriş Yap  ]                │
└────────────────────────────────────────┘
```

### Yönlendirme mantığı:

```razor
@code {
    [SupplyParameterFromQuery]
    public string? ReturnUrl { get; set; }

    private async Task HandleLogin()
    {
        var token = _authService.Authenticate(_username, _password);
        if (token is null) { _error = true; return; }

        var role = _authService.GetRole(_username)!;
        await _authProvider.LoginAsync(token, _username, role);

        // Kullanıcı /degerlendirme'ye giderken /login'e yönlendirildiyse,
        // başarılı girişte doğrudan o sayfaya gönder
        var target = string.IsNullOrEmpty(ReturnUrl) ? "/" : ReturnUrl;
        Navigation.NavigateTo(target, forceLoad: false);
    }
}
```

**Önemli:** Parola alanında `Enter` tuşu `HandleLogin()`'i tetiklemek için `@onkeydown` olayına bağlandı. Aksi hâlde kullanıcı Enter'a basınca form gönderilmez — Blazor'un `EditForm` olmadan standart HTML form davranışı devre dışıdır.

---

## Adım 6 — Rota Güvenliği (Auth Guard)

### Components/App.razor güncelleme:

```razor
<!-- Eski (Faz 2) -->
<Routes />

<!-- Yeni (Faz 3) -->
<CascadingAuthenticationState>
    <Router AppAssembly="@typeof(App).Assembly">
        <Found Context="routeData">
            <AuthorizeRouteView RouteData="@routeData"
                                DefaultLayout="@typeof(MainLayout)">
                <NotAuthorized>
                    <RedirectToLogin />
                </NotAuthorized>
            </AuthorizeRouteView>
        </Found>
        <NotFound>
            <PageTitle>Sayfa Bulunamadı</PageTitle>
            <p>Bu sayfa mevcut değil.</p>
        </NotFound>
    </Router>
</CascadingAuthenticationState>
```

### Components/RedirectToLogin.razor:

```razor
@inject NavigationManager Navigation

@code {
    protected override void OnInitialized()
    {
        var currentUri = Navigation.Uri;
        var encodedReturn = Uri.EscapeDataString(
            new Uri(currentUri).PathAndQuery
        );
        Navigation.NavigateTo($"/login?returnUrl={encodedReturn}", forceLoad: false);
    }
}
```

### Sayfa düzeyinde yetkilendirme direktifleri:

```razor
@* Yalnızca giriş yapan herkese açık *@
@attribute [Authorize]

@* Yalnızca admin rolüne açık (AuditLog) *@
@attribute [Authorize(Roles = "admin")]
```

**Test senaryosu:**
1. Çıkış yap → tarayıcı adres çubuğuna `localhost:5000/degerlendirme` yaz
2. Sayfa `/login?returnUrl=%2Fdegerlendirme` adresine yönlenir ✅
3. Giriş yap → sistem `%2Fdegerlendirme`'ye geri döner ✅

---

## Adım 7 — wwwroot/cdss.js (JS Aktivite Takibi)

**Amaç:** Tarayıcıdaki kullanıcı hareketlerini izleyerek boşta kalma süresini ölçmek.

```javascript
// Boşta kalma süresini saniye olarak tutan sayaç
let _idleSeconds = 0;
let _idleTimer   = null;

// Kullanıcı herhangi bir etkileşim yaptığında sayacı sıfırla
function resetIdle() { _idleSeconds = 0; }

window.cdss = {
    startIdleTracking: function () {
        // 1. Kullanıcı aktivitelerini dinle
        ["mousemove", "click", "keydown", "touchstart"].forEach(evt =>
            document.addEventListener(evt, resetIdle, { passive: true })
        );

        // 2. Her saniye sayacı artır
        _idleTimer = setInterval(() => { _idleSeconds++; }, 1000);
    },

    getIdleSeconds: function () {
        return _idleSeconds;
    },

    stopIdleTracking: function () {
        clearInterval(_idleTimer);
    },

    downloadFile: function (fileName, base64Data, mimeType) {
        const link   = document.createElement("a");
        link.href    = `data:${mimeType};base64,${base64Data}`;
        link.download = fileName;
        link.click();
    }
};
```

**Tasarım kararı:** `passive: true` bayrağı `mousemove` ve `touchstart` için kritik. Pasif dinleyici, tarayıcının scroll işlemini JavaScript'in bitmesini beklemeden gerçekleştirmesine izin verir — yüksek frekanslı olaylarda UI donmasını önler.

---

## Adım 8 — Oturum Zaman Aşımı (MainLayout.razor)

**Amaç:** 29. dakikada uyarı, 30. dakikada otomatik çıkış.

### Timer entegrasyonu:

```csharp
private System.Timers.Timer? _sessionTimer;
private bool _showTimeoutWarning = false;
private const int TimeoutMinutes = 30;

protected override async Task OnAfterRenderAsync(bool firstRender)
{
    if (!firstRender) return;

    await JS.InvokeVoidAsync("cdss.startIdleTracking");

    _sessionTimer = new System.Timers.Timer(30_000); // 30 saniyede bir kontrol
    _sessionTimer.Elapsed += async (_, _) => await CheckIdleAsync();
    _sessionTimer.Start();
}
```

### Boşta kalma kontrolü:

```csharp
private async Task CheckIdleAsync()
{
    // System.Timers.Timer thread-safe değil; Blazor circuit'una dön
    await InvokeAsync(async () =>
    {
        int idle;
        try { idle = await JS.InvokeAsync<int>("cdss.getIdleSeconds"); }
        catch { return; } // Bağlantı kopmuşsa sessizce geç

        int idleMinutes = idle / 60;

        if (idleMinutes >= TimeoutMinutes)
        {
            await ForceLogoutAsync();
        }
        else if (idleMinutes >= TimeoutMinutes - 1)
        {
            _showTimeoutWarning = true;
            StateHasChanged();
        }
        else
        {
            _showTimeoutWarning = false;
        }
    });
}
```

**Kritik sorun ve çözümü:**

`System.Timers.Timer.Elapsed` olayı, .NET thread pool'undaki rastgele bir iş parçacığında tetiklenir. Blazor Server'da UI güncellemeleri (`StateHasChanged`) yalnızca circuit thread'inden çağrılabilir; aksi hâlde:

```
System.InvalidOperationException: The current thread is not associated with the
Dispatcher. Use InvokeAsync() to switch execution to the Dispatcher...
```

**Çözüm:** Her timer callback'i `await InvokeAsync(async () => { ... })` ile sarılarak Blazor'un kendi circuit dispatcher'ına yönlendirildi.

### Uyarı modalı:

```razor
@if (_showTimeoutWarning)
{
    <div class="timeout-overlay">
        <div class="timeout-modal">
            <h3>⏱ Oturum Kapanıyor</h3>
            <p>1 dakika içinde işlem yapmazsanız oturumunuz otomatik kapatılacak.</p>
            <button @onclick="ExtendSession">Oturumu Uzat</button>
        </div>
    </div>
}
```

### Temizleme (IAsyncDisposable):

```csharp
public async ValueTask DisposeAsync()
{
    _sessionTimer?.Stop();
    _sessionTimer?.Dispose();
    await JS.InvokeVoidAsync("cdss.stopIdleTracking");
}
```

---

## Adım 9 — Services/PdfReportService.cs (PDF Üretimi)

**Amaç:** Model kararlarını, hasta parametrelerini ve SHAP açıklamalarını içeren tek sayfalık klinik rapor.

### QuestPDF şablon yapısı:

```csharp
Document.Create(container =>
{
    container.Page(page =>
    {
        page.Size(PageSizes.A4);
        page.Margin(2, Unit.Centimetre);
        page.DefaultTextStyle(x => x.FontFamily("Helvetica").FontSize(10));

        page.Header().Element(ComposeHeader);
        page.Content().Element(ComposeContent);
        page.Footer().Element(ComposeFooter);
    });
});
```

### Rapor bölümleri:

| Bölüm | İçerik |
|-------|--------|
| Header | Kurum adı, "KLİNİK KARAR RAPORU", tarih/saat, Hasta ID |
| Klinik Parametreler | PASI, VKİ, LDL, Tırnak Tutulumu, Sabah Tutukluğu, Sigara (tablo) |
| ML Kararı | Her birim için ✅/❌ ikonu + güven skoru çubuğu |
| Yapay Zeka Açıklaması | LLM'den gelen Türkçe klinik yorum metni |
| KVKK Uyarısı | "Bu rapor yardımcı karar destek aracıdır; nihai karar hekime aittir." |
| Footer | Sayfa numarası, model versiyonu, oluşturulma timestamp'i |

### Güven skoru hesaplama (skor düzeltmesi):

```csharp
private static double GetConfidence(LabelDetail label)
{
    // Pozitif karar: olasılık skoru doğrudan kullanılır
    // Negatif karar: "Sistemik Tedavi Gerek Yok — %87 güven" için
    //               1 - P(pozitif) alınır
    return label.Karar
        ? label.Olasilik
        : 1.0 - label.Olasilik;
}
```

**Neden gerekli?** `Olasilik` alanı her zaman "pozitif sınıf olasılığı"dır. Model "Sistemik Tedavi: Hayır" kararı verdiğinde `Olasilik = 0.08` gelir. Bunu doğrudan göstermek "8% güven" izlenimi yaratır; oysa asıl anlam "92% güvenle gerek yok"tur.

### PDF'i Base64'e çevirme:

```csharp
public string GenerateBase64(PredictionResponse pred, PatientInputModel patient)
{
    var doc = BuildDocument(pred, patient);
    var bytes = doc.GeneratePdf();
    return Convert.ToBase64String(bytes);
}
```

---

## Adım 10 — PDF İndirme Mekanizması (Predict.razor)

**Amaç:** Üretilen PDF'i, sunucuya dosya kaydetmeden doğrudan tarayıcıya indirtmek.

### Predict.razor'a eklenenler:

```razor
@inject PdfReportService PdfService
@inject IJSRuntime JS

<!-- Sonuç göründükten sonra buton aktif olur -->
@if (_result is not null)
{
    <button class="btn-download" @onclick="DownloadReport">
        📄 Raporu İndir
    </button>
}

@code {
    private async Task DownloadReport()
    {
        if (_result is null || _currentPatient is null) return;

        _downloadLoading = true;

        var base64 = PdfService.GenerateBase64(_result, _currentPatient);
        var fileName = $"CDSS_{_currentPatient.HastaId}_{DateTime.Now:yyyyMMdd_HHmm}.pdf";

        await JS.InvokeVoidAsync("cdss.downloadFile", fileName, base64, "application/pdf");

        _downloadLoading = false;
    }
}
```

### Akış diyagramı:

```
[Raporu İndir] butonuna tıkla
    → PdfReportService.GenerateBase64()
        → QuestPDF: Document → PDF byte[]
        → Convert.ToBase64String(bytes)
    → JS.InvokeVoidAsync("cdss.downloadFile", ...)
        → Tarayıcıda <a href="data:..."> oluştur
        → .click() → İndirme başlar
    → Sunucuda hiçbir dosya saklanmaz ✅
```

---

## Adım 11 — KVKK Uyumlu Audit Log Ekranı

### Components/Pages/AuditLog.razor:

```razor
@attribute [Authorize(Roles = "admin")]
@page "/audit-log"
```

### KVKK maskeleme — CdssApiService.cs:

```csharp
private static string MaskHastaId(string hastaId)
{
    // "PSO-TEST-001" → "PS*******01"
    if (hastaId.Length <= 4) return new string('*', hastaId.Length);

    return hastaId[..2]
        + new string('*', hastaId.Length - 4)
        + hastaId[^2..];
}
```

**Tasarım kararı:** Maskeleme sunucu tarafında (`CdssApiService` içinde) yapılır. `AuditLog.razor` bileşeni ham hasta ID'yi hiçbir zaman almaz — JavaScript konsoluna bile düşmez.

### Tablo yapısı:

| # | Tarih / Saat | Hasta ID (Maskeli) | Önerilen Birimler | Süre | Model |
|---|-------------|-------------------|-------------------|------|-------|
| 3 | 31.07.2026 09:14 | PS\*\*\*\*\*\*\*01 | 🏃 FTR 🏥 Aile Hek. 💊 Sistemik | 7 ms | v1.0 |

### Filtreleme:

```razor
<input class="filter-input"
       placeholder="Hasta ID ile filtrele..."
       @bind="_filterHastaId"
       @bind:event="oninput"
       @onkeydown="@(e => { if (e.Key == "Enter") LoadLogs(); })" />
```

**Not:** Kullanıcı filtreye maskelenmiş ID (`PS*******01`) değil, tam ID (`PSO-TEST-001`) yazarak arama yapabilir. Maskeleme yalnızca görüntüleme katmanında devreye girer; API sorgusu ham ID ile çalışır.

---

## Adım 12 — Blazor SSR / InteractiveServer Düzeltmesi

**Sorun:** .NET 8'in yeni varsayılan render modu statik SSR'dır. Faz 2'de butonlar tıklanabiliyordu çünkü sayfalar `@rendermode InteractiveServer` direktifi içeriyordu. Faz 3'te eklenen `Login.razor` ve `RedirectToLogin.razor` bu direktifi içermiyordu — butonlar HTML olarak render ediliyor fakat hiçbir olay tetiklenmiyordu.

**Hata belirtisi:**

```
[Çıkış Yap] butonuna tıkla → hiçbir şey olmaz
[Giriş Yap] butonuna tıkla → form gönderilmez, sayfa yenilenir
```

**Çözüm — App.razor düzeyinde global InteractiveServer:**

```razor
<!-- Eski (Faz 2): Her sayfada ayrı direktif -->
@* Predict.razor → @rendermode InteractiveServer *@
@* AuditLog.razor → @rendermode InteractiveServer *@

<!-- Yeni (Faz 3): App.razor'da tek noktadan yönetim -->
<Routes @rendermode="InteractiveServer" />
```

Bu değişiklik ile tüm rotalar — yeni eklenenler dahil — otomatik olarak `InteractiveServer` modunda çalışır; her sayfaya direktif ekleme zorunluluğu ortadan kalkar.

---

## Adım 13 — Responsive Sidebar İyileştirmesi (MainLayout.razor + app.css)

**Sorun:** Faz 3'te Sidebar'a "Çıkış Yap" butonu ve auth bilgisi eklenince, link sayısı arttı; küçük ekranlarda alt öğeler görünmez oldu.

### CSS değişiklikleri:

```css
/* Menü linkleri kaydırılabilir bölge */
.nav-links-container {
    flex: 1;
    overflow-y: auto;
    padding-bottom: 8px;
}

/* Çıkış Yap butonu ekranın dibinde sabit */
.sidebar-footer {
    position: sticky;
    bottom: 0;
    background: var(--bg-secondary);
    padding: 12px 16px;
    border-top: 1px solid #1E2D3D;
    flex-shrink: 0;
}

/* "API Offline" bildirimini sidebar'dan kaldır — Home ekranında yeterli */
.api-status-banner { display: none; }
```

### Kullanıcı bilgisi gösterimi:

```razor
<AuthorizeView>
    <Authorized>
        <div class="sidebar-user">
            <span class="user-role-badge">@context.User.FindFirst(ClaimTypes.Role)?.Value</span>
            <span class="username">@context.User.Identity?.Name</span>
        </div>
    </Authorized>
</AuthorizeView>
```

### NavMenu güncelleme — rol tabanlı görünürlük:

```razor
<!-- Yalnızca admin görebilir -->
<AuthorizeView Roles="admin">
    <a href="/audit-log" class="nav-link">
        <span>📋</span> Audit Log
    </a>
</AuthorizeView>

<!-- Herkes görebilir -->
<AuthorizeView>
    <a href="/degerlendirme" class="nav-link">
        <span>🔬</span> Değerlendirme
    </a>
</AuthorizeView>
```

---

## Adım 14 — Build ve Doğrulama

### Build sonucu:

```bash
cd cdss_web && dotnet build
# Build succeeded.
# 0 Error(s)
# 0 Warning(s)
```

### Uçtan uca test senaryoları:

**Senaryo 1 — Auth Guard:**
```
1. Çıkış yap
2. Tarayıcıya: localhost:5000/degerlendirme
3. Beklenen: /login?returnUrl=%2Fdegerlendirme  ✅
4. Giriş: doktor / cdss2024
5. Beklenen: /degerlendirme sayfasına yönlenir  ✅
```

**Senaryo 2 — Rol kısıtlaması:**
```
1. doktor hesabıyla giriş yap
2. Tarayıcıya: localhost:5000/audit-log
3. Beklenen: /login'e yönlenir (Roles="admin" direktifi) ✅
4. Çıkış yap, admin / admin2024 ile giriş yap
5. Beklenen: Audit Log sayfası açılır ✅
```

**Senaryo 3 — PDF indirme:**
```
1. PSO-TEST-001 ile tahmin yap
2. "Raporu İndir" butonuna tıkla
3. Beklenen: CDSS_PSO-TEST-001_20260731_0914.pdf indirilir ✅
4. PDF'i aç: PASI=12.5, VKİ=33.5, 3 birim kararı görünür ✅
```

**Senaryo 4 — Session timeout uyarısı:**
```
1. Giriş yap, 29 dakika hareketsiz kal (test: JS ile idle'ı zorla)
2. Beklenen: "Oturum Kapanıyor" uyarısı çıkar ✅
3. "Oturumu Uzat" tıkla → uyarı kapanır, sayaç sıfırlanır ✅
4. 30. dakikada: /login'e yönlendir ✅
```

---

## Öğrenilen Dersler

1. **`System.Timers.Timer` + Blazor = `InvokeAsync` zorunlu** — Timer callback'leri thread pool'da çalışır; `StateHasChanged()` veya herhangi bir Blazor UI operasyonu `InvokeAsync` olmadan çağrılırsa circuit exception fırlatır.

2. **`ProtectedSessionStorage` prerendering'de erişilemez** — Blazor Server'ın ilk SSR geçişinde `GetAsync` çöker. `try/catch` içinde `_anonymous` döndürmek zorunludur; SignalR bağlantısı kurulunca state otomatik güncellenir.

3. **`AddScoped<AuthenticationStateProvider, CustomAuthStateProvider>()` sırası önemli** — `AddAuthorizationCore()` ve `AddCascadingAuthenticationState()` ÖNCE çağrılmalı; aksi hâlde provider DI'a kaydedilmiş olsa da `AuthorizeView` çalışmaz.

4. **Global `@rendermode InteractiveServer` (App.razor)** — Sayfalar büyüdükçe her bileşene ayrı direktif eklemek hata kaynağına dönüşür. `<Routes @rendermode="InteractiveServer">` ile tek noktadan yönetim, gözden kaçan SSR-only sayfaları ortadan kaldırır.

5. **QuestPDF güven skoru tersine çevirme** — Modelin `Olasilik` değeri her zaman "pozitif sınıf olasılığı"dır. Negatif kararlar için `1 - Olasilik` alınmadan raporlanırsa, "Sistemik Tedavi: Gerek Yok" kararı "%8 güven" olarak yanlış görünür.

6. **KVKK maskeleme serviste yapılmalı** — Maskelemeyi bileşen katmanında (`AuditLog.razor` içinde) yapmak, ham ID'nin JavaScript konsoluna düşmesine izin verir. Maskeleme `CdssApiService.GetLogsAsync()` içinde, veri ağdan döner dönmez uygulanmalı.

7. **`localhost` vs `127.0.0.1` (Faz 2'den devam)** — Auth token `Authorization: Bearer` header'ında gönderildiğinde macOS'ta `localhost` → IPv6 çözümlemesi FastAPI'nin Token middleware'ini bypass edebilir. `127.0.0.1` kullanımına devam edildi.

---

## Üretilen / Güncellenen Dosyalar (Faz 3 — 11 adet)

```
cdss_web/
├── Program.cs                              ← AddAuthorizationCore, QuestPDF lisans
├── appsettings.json                        ← değişmedi
├── Models/
│   ├── PatientInputModel.cs                ← değişmedi
│   └── PredictionResponse.cs              ← değişmedi
├── Services/
│   ├── CdssApiService.cs                  ← MaskHastaId() eklendi
│   ├── AuthService.cs                     ← YENİ: kullanıcı doğrulama + token üretimi
│   ├── CustomAuthStateProvider.cs         ← YENİ: ProtectedSessionStorage auth
│   └── PdfReportService.cs               ← YENİ: QuestPDF rapor motoru
├── Components/
│   ├── App.razor                          ← CascadingAuthenticationState, InteractiveServer
│   ├── Routes.razor                       ← değişmedi
│   ├── RedirectToLogin.razor              ← YENİ: Auth guard yönlendirmesi
│   ├── _Imports.razor                     ← Authorization namespace'leri eklendi
│   ├── Layout/
│   │   └── MainLayout.razor              ← Timer, timeout modal, sidebar auth bilgisi
│   └── Pages/
│       ├── Home.razor                     ← değişmedi
│       ├── Login.razor                    ← YENİ: Giriş ekranı
│       ├── Predict.razor                  ← PDF indirme butonu eklendi
│       └── AuditLog.razor                ← [Authorize(Roles="admin")] eklendi
└── wwwroot/
    ├── app.css                            ← Sidebar scroll, footer sabit, timeout modal
    └── cdss.js                            ← YENİ: idle tracker + downloadFile
```

---

## Çalıştırma Komutları

```bash
# Terminal 1 — FastAPI Backend
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Blazor Web Arayüzü
cd cdss_web && dotnet run --urls "http://localhost:5000"
```

### Test kullanıcıları:

| Kullanıcı Adı | Şifre | Rol | Erişim |
|---------------|-------|-----|--------|
| `doktor` | `cdss2024` | doktor | Anasayfa, Değerlendirme |
| `admin` | `admin2024` | admin | Tüm sayfalar + Audit Log |

| Sayfa | URL |
|-------|-----|
| 🔑 Giriş | http://localhost:5000/login |
| 🏠 Anasayfa | http://localhost:5000 |
| 🔬 Hasta Değerlendirme | http://localhost:5000/degerlendirme |
| 📋 Audit Log (admin) | http://localhost:5000/audit-log |
| 📖 FastAPI Docs | http://localhost:8000/docs |

---

## Sıradaki Adımlar (Faz 4)

- [ ] Gerçek hasta verisi ETL pipeline'ı — hastane veri formatına özel parser
- [ ] Retrospektif validasyon — eski doktor kararları vs. model çıktıları karşılaştırması
- [ ] Model v2.0 eğitimi — gerçek veriyle, DLQI/BSA/yaş özelliklerini aktifleştirerek
- [ ] Kimlik doğrulama — Hastane AD (Active Directory) / gerçek JWT login entegrasyonu
- [ ] KVKK log şifreleme — audit tablosunda `input_json` alanı AES-256 ile şifrelenmeli
- [ ] PDF rapor geliştirme — SHAP waterfall görselini PDF içine gömmek (SVG → QuestPDF entegrasyonu)
- [ ] İzleme / alerting — Sentry veya Azure Monitor entegrasyonu; model confidence < 0.6 için uyarı

# Faz 4 — Adım Adım Uygulama Kaydı

> **Tarih**: 1–2 Ağustos 2026
> **Amaç**: CDSS'i klinik üretime hazır hâle getirmek — güvenlik katmanlarını endüstri standardına yükseltmek
> **Kapsam**: FastAPI Backend (Python) + .NET 8 Blazor Server (C#)
> **Proje dizini**: `~/Projects/dermatology_project`

---

## Adım 1 — Faz 4 Mimari Kararı

Faz 3 sonunda sistem çalışır durumdaydı; ancak klinik ortamda kabul edilebilir güvenlik standartlarını karşılamıyordu. Faz 4'ün tamamı güvenlik ve dayanıklılık odaklıdır — yeni özellik eklenmedi.

| Karar | Seçim | Gerekçe |
|-------|-------|---------|
| API kimlik doğrulama | OAuth2 Password Flow + JWT | FastAPI'nin native desteği; Blazor → API arası makine kimliği için endüstri standardı |
| Token süresi | 8 saat | Klinik vardiya süresiyle uyumlu; sabah giren hekim akşama kadar yeniden giriş yapmak zorunda kalmaz |
| Şifre saklama | bcrypt (cost factor 12) | Geri döndürülemez, brute-force'a dirençli; SHA-256 (Faz 3) artık yetersiz |
| Veritabanı şifreleme | Fernet (AES-128-CBC + HMAC-SHA256) | Python `cryptography` kütüphanesinin standart simetrik şifreleme primitifi |
| Rate limiting | slowapi (Redis opsiyonel) | FastAPI middleware olarak entegre; in-memory counter, üretimde Redis'e taşınabilir |
| CORS politikası | Strict whitelist | `allow_origins=["*"]` üretimde kabul edilemez; yalnızca Blazor origin'i izin verilir |
| HTTPS zorlama | HSTS + HttpsRedirection | HTTP üzerinden kimlik bilgisi seyahat etmemeli |
| Yedekleme | Tarihli dosya sistemi yedekleri | SQLite için pg_dump yoktur; shutil.copy2 + 30 günlük otomatik temizlik |

---

## Adım 2 — Paket Kurulumu

### Python (FastAPI backend):

```bash
source .venv/bin/activate

pip install \
    "python-jose[cryptography]" \   # JWT oluşturma ve doğrulama
    "passlib[bcrypt]" \             # bcrypt şifre hash'leme
    slowapi \                       # Rate limiting
    cryptography                    # Fernet AES şifreleme
```

### .NET (Blazor frontend):

```bash
cd cdss_web
# Faz 4'te .NET tarafına yeni paket eklenmedi.
# HSTS ve HTTPS yönlendirmesi ASP.NET Core'un yerleşik middleware'i ile yapıldı.
```

### Güncellenen `pyproject.toml` bağımlılık grubu:

```toml
[project.optional-dependencies]
security = [
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "slowapi>=0.1.9",
    "cryptography>=41.0.0",
]
```

---

## Adım 3 — config/settings.py Güncellemesi

**Amaç:** Yeni güvenlik yapılandırmalarını merkezi ayar dosyasına eklemek.

### Eklenen alanlar:

```python
class Settings(BaseSettings):
    # ... mevcut alanlar ...

    # JWT
    SECRET_KEY: str = "DEGISTIR_URETIMDE_GUCLU_KEY_KUL"  # .env'den okunur
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 saat

    # Fernet şifreleme
    ENCRYPTION_KEY: str = ""  # .env'den okunur; boşsa şifreleme devre dışı

    # Rate limiting
    RATE_LIMIT_TOKEN: str = "10/minute"    # /token endpoint
    RATE_LIMIT_PREDICT: str = "5/minute"   # /predict endpoint

    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5000",
        "http://localhost:5285",
        "https://cdss.hastane.local",  # üretim adresi
    ]
```

### .env.example güncellemesi:

```
GEMINI_API_KEY=...
DATABASE_URL=sqlite:///./audit.db
API_HOST=0.0.0.0
API_PORT=8000
LLM_ENABLED=true
RANDOM_SEED=42

# Faz 4 — Güvenlik
SECRET_KEY=buraya-en-az-32-karakter-rastgele-bir-dize-girin
ENCRYPTION_KEY=buraya-fernet-generate-ile-uretilmis-key-girin
```

### Fernet anahtarı üretimi (tek seferlik):

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Çıktı: XyZ1a2B3c4D5e6F7g8H9i0J1k2L3m4N5o6P7q8R9=
# Bu değeri .env dosyasına ENCRYPTION_KEY= olarak yapıştır
```

> **Kritik:** `ENCRYPTION_KEY` kaybolursa veritabanındaki şifreli veriler kalıcı olarak
> okunamaz hâle gelir. Anahtar yedeklemesi `.env` dosyasından bağımsız, güvenli bir
> kasada saklanmalıdır.

---

## Adım 4 — api/security.py (JWT + bcrypt Çekirdeği)

**Amaç:** Kimlik doğrulama mantığını `api/main.py`'den ayırmak ve tek bir modülde toplamak.

### Kullanıcı deposu (Faz 4 statik, Faz 5'te veritabanına taşınacak):

```python
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Şifreler artık açık metin değil; önceden hash'lenmiş değerler saklanır.
# Hash üretimi: pwd_context.hash("cdss2024")
USERS_DB = {
    "doktor": {
        "username": "doktor",
        "hashed_password": "$2b$12$XXXX...",  # bcrypt hash
        "role": "doktor",
    },
    "admin": {
        "username": "admin",
        "hashed_password": "$2b$12$YYYY...",  # bcrypt hash
        "role": "admin",
    },
}
```

### Doğrulama ve token üretimi:

```python
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def authenticate_user(username: str, password: str) -> dict | None:
    user = USERS_DB.get(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
```

### Token doğrulama (dependency):

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik doğrulaması başarısız",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = USERS_DB.get(username)
    if user is None:
        raise credentials_exception
    return user
```

---

## Adım 5 — /token Endpoint'i (api/main.py)

**Amaç:** Kullanıcı adı ve şifreyi alıp JWT döndüren kimlik doğrulama kapısı.

```python
from fastapi.security import OAuth2PasswordRequestForm

@app.post("/token")
@limiter.limit(settings.RATE_LIMIT_TOKEN)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer"}
```

### Korunan endpoint örneği:

```python
@app.post("/predict")
@limiter.limit(settings.RATE_LIMIT_PREDICT)
async def predict(
    request: Request,
    patient: PatientInput,
    current_user: dict = Depends(get_current_user),  # ← JWT zorunlu
):
    ...
```

Faz 3'te `Authorization: Bearer cdss-dev-token-2024` sabit stringi kabul ediliyordu. Faz 4'te her endpoint `get_current_user` bağımlılığını taşır; geçersiz veya süresi dolmuş token `HTTP 401` döndürür ve işlem durur.

---

## Adım 6 — Services/CdssApiService.cs Güncellemesi (Token Akışı)

**Amaç:** Blazor'un Faz 3'teki sabit `appsettings.json` token'ı yerine API'den dinamik JWT almasını sağlamak.

### Oturum açma isteği:

```csharp
public async Task<string?> GetTokenAsync(string username, string password)
{
    // OAuth2 Password Flow — application/x-www-form-urlencoded formatı zorunlu
    var form = new FormUrlEncodedContent(new[]
    {
        new KeyValuePair<string, string>("username", username),
        new KeyValuePair<string, string>("password", password),
        new KeyValuePair<string, string>("grant_type", "password"),
    });

    var response = await _httpClient.PostAsync("/token", form);

    if (!response.IsSuccessStatusCode) return null;

    var json = await response.Content.ReadAsStringAsync();
    var result = JsonSerializer.Deserialize<TokenResponse>(json);
    return result?.AccessToken;
}
```

**Önemli:** `/token` endpoint'i `application/json` değil `application/x-www-form-urlencoded` bekler. Bu, OAuth2 standardının gereğidir. `JsonContent` ile gönderilen Faz 3 isteği `422 Unprocessable Entity` döndürür — `FormUrlEncodedContent` zorunludur.

### Token yönetimi (CustomAuthStateProvider.cs güncelleme):

```csharp
// Faz 3: appsettings.json'dan sabit token okunuyordu
// Faz 4: API'den alınan JWT, ProtectedSessionStorage'a yazılıyor

public async Task LoginAsync(string username, string password)
{
    var token = await _apiService.GetTokenAsync(username, password);
    if (token is null) throw new UnauthorizedAccessException();

    await _storage.SetAsync("cdss_jwt", token);
    // Claims artık JWT payload'ından parse ediliyor
    var claims = ParseJwtClaims(token);
    NotifyAuthenticationStateChanged(...);
}
```

### Her istekte token enjeksiyonu:

```csharp
// Faz 3: appsettings.json'daki sabit string
// Faz 4: Storage'dan okunan dinamik JWT

private async Task<HttpRequestMessage> CreateRequestAsync(HttpMethod method, string endpoint)
{
    var tokenResult = await _storage.GetAsync<string>("cdss_jwt");
    var request = new HttpRequestMessage(method, endpoint);

    if (tokenResult.Success && !string.IsNullOrEmpty(tokenResult.Value))
        request.Headers.Authorization =
            new AuthenticationHeaderValue("Bearer", tokenResult.Value);

    return request;
}
```

---

## Adım 7 — audit/encryption.py (Fernet AES Şifreleme)

**Amaç:** Veritabanına yazılacak hassas alanları şifrelemek; okurken çözmek.

### Şifreleme modülü:

```python
from cryptography.fernet import Fernet, InvalidToken

class AuditEncryptor:
    def __init__(self, key: str):
        # Key boşsa şifreleme devre dışı — geliştirme ortamı için
        self._fernet = Fernet(key.encode()) if key else None

    def encrypt(self, plaintext: str) -> str:
        if self._fernet is None:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if self._fernet is None:
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            # Yanlış key veya bozuk veri — ham değeri döndür, uyar
            logger.warning("Şifre çözme başarısız — ham değer döndürülüyor")
            return ciphertext
```

**Tasarım kararı:** `ENCRYPTION_KEY` boşsa (`""`) şifreleme tamamen devre dışı kalır. Bu, `.env` dosyası olmayan CI/CD pipeline'larında ve geliştirme ortamlarında testlerin kırılmadan çalışmasını sağlar.

### Şifrelenen alanlar (audit/logger.py güncellemesi):

```python
# Faz 3: Ham JSON yazılıyordu
# Faz 4: Hassas alanlar şifrelenerek yazılıyor

encryptor = AuditEncryptor(settings.ENCRYPTION_KEY)

db.execute("""
    INSERT INTO audit_log (
        timestamp, hasta_id, model_version,
        input_json,          -- ← şifreli
        shap_json,           -- ← şifreli
        llm_explanation,     -- ← şifreli
        pred_ftr, pred_aile, pred_sistemik,
        prob_ftr, prob_aile, prob_sistemik,
        processing_time_ms
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    timestamp, hasta_id, model_version,
    encryptor.encrypt(json.dumps(input_dict)),   # hasta özellikleri
    encryptor.encrypt(json.dumps(shap_dict)),    # SHAP değerleri
    encryptor.encrypt(llm_text),                 # LLM açıklaması
    ...
))
```

### Okuma sırasında çözme (/audit/logs endpoint'i):

```python
@app.get("/audit/logs")
async def get_logs(current_user: dict = Depends(get_current_user)):
    rows = db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()
    return [
        {
            **row,
            "input_json":      encryptor.decrypt(row["input_json"]),
            "shap_json":       encryptor.decrypt(row["shap_json"]),
            "llm_explanation": encryptor.decrypt(row["llm_explanation"]),
        }
        for row in rows
    ]
```

### Veritabanında şifreli verinin görünümü:

```
input_json: gAAAAABm1k3X9aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV2wX3yZ...
shap_json:  gAAAAABm1k3XpQ8rS9tU0vW1xY2zA3bB4cC5dD6eE7fF8gG9hH0...
```

Sunucu diski ele geçirilse veya veritabanı dosyası kopyalansa bile içerik okunamaz.

---

## Adım 8 — Rate Limiting (slowapi)

**Amaç:** Kaba kuvvet (brute force) ve servis dışı bırakma (DoS) saldırılarına karşı koruma.

### FastAPI entegrasyonu:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### Limit tanımları:

| Endpoint | Limit | Gerekçe |
|----------|-------|---------|
| `POST /token` | 10/dakika | Şifre deneme saldırısına karşı |
| `POST /predict` | 5/dakika | Hesaplamalı yük; her tahmin ~7ms model + LLM süresi |
| `GET /health` | 30/dakika | Monitoring araçları sık çağırır; çok dar olmamalı |
| `GET /audit/logs` | 20/dakika | Admin kullanımı; dar limit gereksiz |

### Limit aşıldığında dönen yanıt:

```json
HTTP 429 Too Many Requests

{
  "error": "Rate limit exceeded: 10 per 1 minute"
}
```

**Konfigürasyon notu:** `slowapi` varsayılan olarak IP bazlı in-memory sayaç kullanır. Üretimde birden fazla sunucu instance'ı varsa (yük dengeleme), sayaçlar instance'lar arasında paylaşılmaz. Bu durumda Redis backend'i gerekir:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379",  # Faz 5 için hazır
)
```

---

## Adım 9 — CORS Sıkılaştırması (api/main.py)

**Amaç:** API'ye yalnızca bilinen Blazor origin'lerinden istek kabul etmek.

### Faz 3 (güvensiz):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # ← internetteki her site istek atabilir
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Faz 4 (sıkı whitelist):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # ← yalnızca tanımlı adresler
    allow_credentials=True,
    allow_methods=["GET", "POST"],           # ← yalnızca kullanılan metodlar
    allow_headers=["Authorization", "Content-Type"],
)
```

### settings.py ALLOWED_ORIGINS:

```python
ALLOWED_ORIGINS: list[str] = [
    "http://localhost:5000",
    "http://localhost:5285",
    "https://cdss.hastane.local",
]
```

**Dikkat:** `allow_credentials=True` ile `allow_origins=["*"]` birlikte kullanılamaz — CORS standardı bunu yasaklar ve tarayıcı isteği engeller. Whitelist zorunlu hâle gelir.

---

## Adım 10 — HSTS ve HTTPS Zorlama (Program.cs)

**Amaç:** Kullanıcı `http://` ile erişmeye çalışsa bile trafiği şifreli kanala yönlendirmek.

### Program.cs güncellemesi:

```csharp
var app = builder.Build();

// Üretimde HTTPS yönlendirme zorunlu
if (!app.Environment.IsDevelopment())
{
    app.UseHsts();          // HSTS header'ı ekler: max-age=31536000
}

app.UseHttpsRedirection(); // HTTP → HTTPS yönlendirme (geliştirmede de aktif)

// ... geri kalan middleware sırası değişmedi ...
app.UseAuthentication();
app.UseAuthorization();
app.MapRazorComponents<App>().AddInteractiveServerRenderMode();
```

### HSTS header'ının tarayıcıya etkisi:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

Bu header'ı bir kez alan tarayıcı, sonraki 1 yıl boyunca aynı domain için HTTP isteklerini sunucuya göndermeden otomatik HTTPS'e çevirir — man-in-the-middle saldırılarına karşı ek katman.

**Geliştirme notu:** `app.Environment.IsDevelopment()` kontrolü, lokal ortamda (`localhost`) HSTS'nin devreye girmesini önler. HSTS bir kez `localhost` için set edilirse tarayıcıyı temizlemeden kaldırmak zordur — `if (!IsDevelopment())` koruması kritik.

---

## Adım 11 — scripts/backup.py (Otomatik Yedekleme)

**Amaç:** Veritabanı bozulması veya yanlışlıkla silme durumuna karşı günlük yedek almak.

### Yedekleme mantığı:

```python
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import logging

BACKUP_DIR  = Path("backups")
DB_PATH     = Path("audit.db")
KEEP_DAYS   = 30

def backup():
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"audit_{timestamp}.db"

    shutil.copy2(DB_PATH, dest)
    logging.info(f"Yedek alındı: {dest}")

def cleanup_old_backups():
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    removed = 0
    for f in BACKUP_DIR.glob("audit_*.db"):
        # Dosya adından tarihi çıkar: audit_20260801_093000.db
        try:
            date_str = f.stem.split("_", 1)[1]  # "20260801_093000"
            file_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
            if file_date < cutoff:
                f.unlink()
                removed += 1
        except ValueError:
            continue
    if removed:
        logging.info(f"{removed} eski yedek silindi (>{KEEP_DAYS} gün)")

if __name__ == "__main__":
    backup()
    cleanup_old_backups()
```

### Kullanım:

```bash
# Manuel yedek
python scripts/backup.py

# Çıktı:
# INFO: Yedek alındı: backups/audit_20260801_093000.db
# INFO: 2 eski yedek silindi (>30 gün)
```

### Otomatik zamanlama (cron — macOS/Linux):

```bash
crontab -e

# Her gün gece 02:00'de yedek al
0 2 * * * cd ~/Projects/dermatology_project && .venv/bin/python scripts/backup.py >> logs/backup.log 2>&1
```

### Yedek dizin yapısı (örnek):

```
backups/
├── audit_20260801_020000.db
├── audit_20260802_020000.db
├── ...
└── audit_20260831_020000.db   ← En güncel; 30 gün öncesi otomatik silinir
```

**Tasarım kararı:** SQLite için `shutil.copy2` kullanımı, `sqlite3` modülünün `.backup()` metoduna tercih edildi. Neden: `shutil.copy2`, dosyanın metadata'sını (oluşturma/değiştirme zamanı) korur; SQLite `.backup()` ise aktif yazma işlemleri varsa kilitlenme riski taşır. Klinik ortamda API sürekli çalışırken yedek alınacağından `shutil.copy2` daha güvenli.

---

## Adım 12 — Login.razor Güncellemesi (Blazor)

**Amaç:** Faz 3'teki statik kimlik doğrulamayı kaldırmak, API tabanlı JWT akışına geçmek.

### Faz 3 akışı (kaldırıldı):

```
Kullanıcı → Blazor içinde string karşılaştırma → ProtectedSessionStorage
```

### Faz 4 akışı:

```
Kullanıcı → Blazor → POST /token → JWT → ProtectedSessionStorage
```

### Login.razor güncellenen `HandleLogin`:

```razor
@code {
    private async Task HandleLogin()
    {
        _loading = true;
        _error = null;

        try
        {
            // API'ye gönder, JWT al
            var token = await ApiService.GetTokenAsync(_username, _password);
            if (token is null)
            {
                _error = "Kullanıcı adı veya şifre hatalı.";
                return;
            }
            // JWT'yi storage'a yaz, state'i güncelle
            await AuthProvider.LoginWithTokenAsync(token);

            var target = string.IsNullOrEmpty(ReturnUrl) ? "/" : ReturnUrl;
            Navigation.NavigateTo(target, forceLoad: false);
        }
        catch (HttpRequestException)
        {
            _error = "API'ye bağlanılamıyor. Lütfen sistem yöneticisine başvurun.";
        }
        finally
        {
            _loading = false;
        }
    }
}
```

**Yeni UI öğesi:** Giriş denemesi sırasında buton `_loading = true` ile devre dışı bırakılır, metin "Giriş Yapılıyor..." olarak güncellenir. Çift tıklama ile iki paralel `/token` isteği gönderilmesi önlenir.

---

## Adım 13 — Build ve Doğrulama

### Python testleri:

```bash
source .venv/bin/activate
pytest tests/ -v

# ===================== 24 passed, 0 warnings =====================
```

### .NET build:

```bash
cd cdss_web && dotnet build
# Build succeeded. 0 Error(s), 0 Warning(s)
```

### Uçtan uca güvenlik test senaryoları:

**Senaryo 1 — JWT zorunluluğu:**
```bash
# Token olmadan /predict isteği
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"hasta_id":"PSO-001", ...}'

# HTTP 401 Unauthorized
# {"detail": "Not authenticated"}  ✅
```

**Senaryo 2 — Token alımı ve kullanımı:**
```bash
# /token'dan JWT al
curl -X POST http://localhost:8000/token \
  -d "username=doktor&password=cdss2024&grant_type=password"
# {"access_token": "eyJ...", "token_type": "bearer"}  ✅

# Token ile /predict isteği
curl -X POST http://localhost:8000/predict \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"hasta_id":"PSO-001", ...}'
# HTTP 200 + tahmin sonucu  ✅
```

**Senaryo 3 — Rate limiting:**
```bash
# 11. /token isteğinde (dakikada 10 limit)
# HTTP 429 Too Many Requests
# {"error": "Rate limit exceeded: 10 per 1 minute"}  ✅
```

**Senaryo 4 — Şifreli veritabanı:**
```bash
sqlite3 audit.db "SELECT input_json FROM audit_log LIMIT 1;"
# gAAAAABm1k3X9aB2cD3eF4gH5iJ6kL7...  ✅ (açık metin değil)
```

**Senaryo 5 — CORS kısıtlaması:**
```bash
# İzin verilmeyen origin'den istek
curl -H "Origin: http://kotu-site.com" http://localhost:8000/predict
# HTTP 400 Bad Request (CORS policy violation)  ✅
```

**Senaryo 6 — Yedekleme:**
```bash
python scripts/backup.py
ls backups/
# audit_20260801_093000.db  ✅
```

---

## Öğrenilen Dersler

1. **`FormUrlEncodedContent` vs `JsonContent` — OAuth2'de zorunlu** — FastAPI'nin `/token` endpoint'i OAuth2 standardı gereği `application/x-www-form-urlencoded` bekler. `JsonContent` ile gönderilen istek `422 Unprocessable Entity` döndürür; hata mesajı yanıltıcıdır.

2. **`allow_credentials=True` + `allow_origins=["*"]` birlikte kullanılamaz** — CORS standardı bu kombinasyonu yasaklar. Tarayıcı isteği sessizce engeller, hata mesajı belirsizdir. Whitelist zorunlu hâle gelince `appsettings.json` ve `.env` koordinasyonu kritik önem kazanır.

3. **`shutil.copy2` vs `sqlite3.backup()` — aktif veritabanı için** — API çalışırken alınan `sqlite3.backup()` kilitleme (lock) nedeniyle başarısız olabilir. `shutil.copy2` dosyayı işletim sistemi seviyesinde kopyaladığı için SQLite'ın uygulama kilidini atlatır; üretimde daha güvenilir.

4. **`ENCRYPTION_KEY` olmadan test ortamı kırılmamalı** — `Fernet(key)` boş string ile başlatılırsa `ValueError` fırlatır. `if key else None` pattern'i ile şifreli ve şifresiz mod arasında şeffaf geçiş sağlanır; CI/CD ortamında `.env` olmadan testler çalışmaya devam eder.

5. **bcrypt cost factor dengesi** — `cost=12` seçimi, hash süresini ~300ms'ye taşır. Giriş sıklığı düşük (hekim sabah bir kez giriş yapar) olan bu sistemde kabul edilebilir; `cost=14` (~1200ms) gereksiz yavaşlık yaratır.

6. **HSTS ve `IsDevelopment()` kontrolü** — HSTS bir kez `localhost` için set edilirse tarayıcı geçmişini temizlemeden kaldırmak güçtür. Geliştirme ortamında HSTS'yi bypass eden `if (!IsDevelopment())` koruması ihmal edilmemeli.

7. **Rate limit in-memory sayacı çoklu instance'ta paylaşılmaz** — `slowapi` varsayılan in-memory backend ile tek sunucu için yeterlidir. Yük dengeleyici arkasında birden fazla instance çalışıyorsa Redis backend zorunludur; bu durum Faz 5 için not edildi.

---

## Üretilen / Güncellenen Dosyalar (Faz 4 — 10 adet)

```
dermatology_project/
├── .env.example                        ← SECRET_KEY, ENCRYPTION_KEY eklendi
├── config/
│   └── settings.py                    ← JWT, ENCRYPTION_KEY, CORS, rate limit ayarları
├── api/
│   ├── main.py                        ← /token endpoint, JWT bağımlılığı, CORS güncellendi
│   └── security.py                    ← YENİ: bcrypt, JWT üretimi/doğrulaması
├── audit/
│   ├── logger.py                      ← Fernet ile şifreli alan yazımı
│   └── encryption.py                  ← YENİ: AuditEncryptor (Fernet AES-128)
├── scripts/
│   └── backup.py                      ← YENİ: Tarihli yedekleme + 30 gün temizlik
└── cdss_web/
    ├── Program.cs                     ← UseHsts(), UseHttpsRedirection()
    ├── Services/
    │   ├── CdssApiService.cs          ← GetTokenAsync(), dinamik JWT enjeksiyonu
    │   └── CustomAuthStateProvider.cs ← LoginWithTokenAsync() — API tabanlı akış
    └── Components/Pages/
        └── Login.razor                ← API çağrısı, _loading state, hata yönetimi
```

---

## Çalıştırma Komutları

```bash
# Terminal 1 — FastAPI Backend
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Blazor Web Arayüzü
cd cdss_web && dotnet run --urls "http://localhost:5000"

# Yedekleme (cron dışında manuel)
python scripts/backup.py
```

### Test kullanıcıları (bcrypt hash'lenmiş şifreler):

| Kullanıcı Adı | Şifre | Rol | Erişim |
|---------------|-------|-----|--------|
| `doktor` | `cdss2024` | doktor | Anasayfa, Değerlendirme |
| `admin` | `admin2024` | admin | Tüm sayfalar + Audit Log |

> Şifreler artık bellekte açık metin olarak değil, `security.py` içinde bcrypt hash olarak tutuluyor.

| Sayfa / Endpoint | URL |
|-----------------|-----|
| 🔑 Giriş | http://localhost:5000/login |
| 🏠 Anasayfa | http://localhost:5000 |
| 🔬 Hasta Değerlendirme | http://localhost:5000/degerlendirme |
| 📋 Audit Log (admin) | http://localhost:5000/audit-log |
| 🔐 Token alma | http://localhost:8000/token |
| 📖 FastAPI Docs | http://localhost:8000/docs

---

---

# Faz 5 — RAG v2: Klinik Kılavuz Danışmanı

> **Tarih**: Eylül 2026
> **Amaç**: SEDA'ya kılavuz tabanlı soru-cevap yeteneği kazandırmak — XGBoost modeli sevk kararı verirken, RAG sistemi "neden?" sorusunu yanıtlar
> **Mimari**: Retrieval-Augmented Generation (RAG) — ChromaDB + Gemini Embedding + Gemini 3.5 Flash
> **Proje dizini**: `~/Projects/dermatology_project/rag/`

---

## Neden RAG? Motivasyon

SEDA v1–v4, bir hastanın hangi klinik birime sevk edileceğini deterministik olarak belirliyordu. Ancak klinikte buna ek olarak kritik bir bilgi boşluğu vardı:

```
"PASI > 10 neden sistemik tedavi eşiği?"
"Bimekizumab bu hasta profilinde tercih edilmeli mi?"
"Psoriatik artrit şüphesinde hangi eklem değerlendirmesi yapılmalı?"
"Gebelikte hangi biyolojikler güvenli?"
```

Bu sorular ML modeli tarafından yanıtlanamaz. Faz 5, 550+ sayfalık resmi kılavuz metinlerinden anlık, kaynaklı ve Türkçe klinik yanıtlar üretmek için **Retrieval-Augmented Generation (RAG)** mimarisini hayata geçirdi.

---

## Adım 1 — Mimari Karar

| Bileşen | Seçim | Gerekçe |
|---------|-------|---------|
| PDF okuma | `pdfplumber` | Kelime düzeyinde font boyutu → otomatik başlık tespiti |
| Embedding modeli | `gemini-embedding-001` | Türkçe + İngilizce aynı vektör uzayı (çokdilli) |
| Vektör veritabanı | ChromaDB (kalıcı) | Sıfır altyapı gereksinimi, disk üzerinde HNSW |
| Mesafe metriği | Cosine | Anlam benzerliği, vektör büyüklüğünden bağımsız |
| Koleksiyon sayısı | 1 (tek) | Metadata filtresi ile kaynak ayrımı; cross-source retrieval kolay |
| QA / Üretim modeli | `gemini-3.6-flash` | Hız + maliyet + Türkçe sentez kalitesi |
| QA sıcaklık | `0.1` | Klinik bağlılık, düşük yaratıcılık sapması |

---

## Adım 2 — Veri Kaynakları (`rag/config.py`)

Sistem iki resmi kılavuzu indeksler:

| Kod | Kaynak | Dil | Konum |
|-----|--------|-----|-------|
| `TR2025` | Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD) | Türkçe | `docs/guidelines/psoriasiskitap2025_SONrenkli.pdf` |
| `EG2025` | EuroGuiDerm — Systemic Treatment of Psoriasis Vulgaris 2025 | İngilizce | `docs/guidelines/Guidelinelar.pdf` |

Tüm sabitler tek bir dosyadan yönetilir — sihirli sayılar koda gömülmez:

```python
CHUNK_SIZE_WORDS       = 280    # ≈ 350 token → 5 chunk → ~2.000 token bağlam
CHUNK_OVERLAP_WORDS    = 40     # Ardışık chunk'lar arası örtüşme
MIN_CHUNK_WORDS        = 25     # Bu eşiğin altındaki sayfalar atlanır (grafik vb.)
EMBEDDING_MODEL        = "models/gemini-embedding-001"
EMBEDDING_BATCH_SIZE   = 10     # Free tier için güvenli batch boyutu
EMBEDDING_DELAY_SEC    = 2.0    # Rate limit koruması: batch aralarında 2s bekleme
TOP_K                  = 5      # En iyi 5 chunk döndürülür
MAX_DISTANCE_THRESHOLD = 0.75   # Bu üstündeki hit'ler ilgisiz kabul edilir
QA_MODEL               = "gemini-3.6-flash"
QA_TEMPERATURE         = 0.1
QA_MAX_OUTPUT_TOKENS   = 3500
```

---

## Adım 3 — PDF Çıkarıcı (`rag/extractor.py`)

**Amaç:** Ham PDF sayfalarını temizlenmiş metin ve zengin metadata'ya dönüştürmek.

### Neden `pdfplumber`?

pdfplumber, diğer PDF kütüphanelerinden farklı olarak **kelime düzeyinde font boyutu bilgisi** sağlar. Bu, bölüm başlıklarını otomatik tespit etmek için kritiktir — büyük fontlu satırlar içerik metniyle karışmamalıdır.

### Gürültü Temizleme (Kaynak Bazlı Regex)

Her kılavuzun tekrarlayan header/footer kalıpları temizlenir:

```python
_NOISE_PATTERNS = {
    "TR2025": [
        r"www\.psokid\.org\s*",
        r"Türkiye\s+Psoriasis\s+Tedavi\s+Kılavuzu\s*[-–]\s*202[0-9]\s*",
        r"^\s*\d{1,3}\s*$",   # tek başına sayfa numarası
    ],
    "EG2025": [
        r"EUROGUIDERM\s+GUIDELINE\s+FOR\s+THE\b.*",
        r"CC\s+BY\s+NC\s+©\s+EDF[^\n]*",
        r"^\s*\d{1,3}\s*$",
    ],
}
```

### Başlık Tespiti (İki Aşamalı Heuristic)

```python
# Birincil: font boyutu bazlı
heading_threshold = median_font_size * 1.30  # Medyanın %130'undan büyük fontlar
# Yedek: ALL CAPS + noktasız kısa satır
upper_ratio > 0.6 and not s.endswith(".")
```

### Çıktı Veri Yapısı

```python
@dataclass
class PageData:
    source_code: str   # 'TR2025' veya 'EG2025'
    pdf_index:   int   # PDF'deki 0 tabanlı sıra
    doc_page:    int   # Kılavuzun görünen sayfa numarası (atıf için kritik)
    heading:     str   # Tespit edilen bölüm başlığı
    text:        str   # Temizlenmiş ham metin
    word_count:  int   # Kelime sayısı
```

---

## Adım 4 — Metin Parçalayıcı (`rag/chunker.py`)

**Amaç:** Sayfa metinlerini anlam bütünlüğünü koruyarak küçük, örtüşen parçalara bölmek.

### Strateji Karşılaştırması

| Strateji | Sorun |
|----------|-------|
| Sabit karakter bölümü | Paragraf ortasında keser — anlam kaybolur |
| Cümle bazlı bölüm | Bazen çok küçük, bazen çok büyük chunk üretir |
| **Kelime bazlı örtüşmeli pencere (seçilen)** | Paragraf sınırlarına saygı + bağlam sürekliliği ✅ |

### Algoritma

```
1. Her sayfanın metni önce paragraflara (\n\n ile) bölünür
2. Paragraf kelimeleri kayan pencereye eklenir
3. Pencere 280 kelimeyi aşınca chunk kaydedilir
4. Son 40 kelimeyle yeni pencere başlatılır (örtüşme)
5. Sayfa sonu örtüşmeyi sıfırlamaz — sayfa kenarındaki cümleler bölünmez
```

**Chunk Kimliği:** `TR2025_p34_c2` → kaynak + görünen sayfa + sıra. Benzersiz ve deterministic.

```python
@dataclass
class Chunk:
    chunk_id:    str   # 'TR2025_p34_c2'
    source_code: str
    heading:     str
    doc_page:    int
    text:        str
    word_count:  int
```

---

## Adım 5 — Gömme Motoru (`rag/embedder.py`)

**Amaç:** Metin chunk'larını 768 boyutlu sayısal vektörlere dönüştürmek.

### Kritik Tasarım: İki Farklı Görev Türü

RAG sistemlerinde embedding'in iki farklı rolü vardır ve Gemini bunları ayrı optimize eder:

| Rol | Task Type | Ne zaman? |
|-----|-----------|-----------|
| Belge indexleme | `RETRIEVAL_DOCUMENT` | Chunk'ları ChromaDB'ye yazarken |
| Sorgu gömme | `RETRIEVAL_QUERY` | Hekimin sorusunu embed ederken |

Bu ayrım retrieval doğruluğunu belirgin şekilde artırır.

### Çokdilli Üstünlük

`gemini-embedding-001`, Türkçe (TR2025) ve İngilizce (EG2025) metinleri **aynı vektör uzayında** temsil eder. Tek sorguda her iki kaynaktan anlamlı sonuçlar alınabilir.

### Rate Limit Yönetimi

```python
EMBEDDING_BATCH_SIZE = 10   # Free tier için güvenli batch boyutu
EMBEDDING_DELAY_SEC  = 2.0  # Batch'ler arası 2 saniye bekleme

# Üstel + kota-duyarlı retry:
if "429" in err_str or "quota" in err_str:
    wait = 15 + (attempt * 10)   # 15s → 25s → 35s → ...
else:
    wait = 2 ** attempt           # 1s → 2s → 4s → ...
# Maksimum 6 deneme
```

---

## Adım 6 — Vektör Veritabanı (`rag/store.py`)

**Amaç:** Chunk embedding'lerini disk üzerinde kalıcı olarak saklamak; hızlı benzerlik sorgusu sağlamak.

### Tek Koleksiyon Kararı

İki kılavuz için iki ayrı koleksiyon yerine **tek koleksiyon** (`seda_guidelines`) seçildi:

- Kaynak filtrelemesi metadata ile: `{"source_code": {"$in": ["TR2025"]}}`
- Tek sorguda iki kaynaktan sonuç alınabilir (cross-source retrieval)
- Ekstra karmaşıklık ortadan kalkar

### Cosine Distance

```python
self._collection = self._client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},  # L2 yerine cosine — metin benzerliği için daha doğru
)
```

Cosine distance vektörün büyüklüğünden bağımsız olarak **yön (anlam) benzerliğini** ölçer.
Aralık: 0 (özdeş anlam) → 2 (tamamen zıt anlam).

### Disk Yapısı

```
rag/chroma_db/
├── 74c34421-0e91-4037-a558-f255c5b7cf60/
│   ├── data_level0.bin    ← HNSW indeks vektörleri
│   ├── header.bin
│   ├── length.bin
│   └── link_lists.bin     ← Approximate Nearest Neighbor graf yapısı
└── chroma.sqlite3         ← Metadata ve döküman metinleri
```

---

## Adım 7 — Retriever (`rag/retriever.py`)

**Amaç:** Hekimin sorusunu alıp en ilgili kılavuz bölümlerini döndürmek.

### Retrieval Pipeline

```
Soru (serbest metin)
    ↓ embed_query() [RETRIEVAL_QUERY task]
Sorgu Vektörü (768 boyut)
    ↓ ChromaDB.query(top_k + 2)       ← +2: filtre kayıplarına karşı tampon
Raw Hits (distance'a göre sıralı)
    ↓ Distance threshold filtresi      (max 0.75 — ilgisiz soru → found=False)
    ↓ Sayfa bazlı çeşitlilik           (aynı sayfadan max 2 chunk)
    ↓ Top-K kesme                      (varsayılan 5)
RetrievalResult listesi
```

### Halüsinasyon Önleme: Distance Threshold

```python
MAX_DISTANCE_THRESHOLD = 0.75
# Cosine distance > 0.75 → ilgisiz kabul edilir
# found=False → QA Engine hiç çağrılmaz
# Konu dışı sorulara uydurma yanıt üretilmez
```

### Benzerlik Yüzdesi (UI'da görüntülenir)

```python
@property
def similarity_pct(self) -> int:
    # cosine distance ∈ [0, 2]; 0 = aynı, 2 = zıt
    return max(0, int((2.0 - self.distance) / 2.0 * 100))
# Örnek: distance=0.32 → %84 benzerlik
```

---

## Adım 8 — QA Motoru (`rag/qa_engine.py`)

**Amaç:** Retrieval bağlamı + hekim sorusu → yapılandırılmış Türkçe klinik yanıt.

### Kritik Tasarım Notu — Sistem Promptu

> Kötü bir system prompt RAG'ı anlamsız hale getirir. LLM ya bağlamın dışına çıkarak hallüsinasyon üretir (çok gevşek), ya da bağlamda açıkça yazılı şeyleri dahi söylemekten kaçınır (çok katı). Doğru denge: "SADECE bu bağlamdan cevap ver, ama cevabı kendi kelimelerinle yaz."

### Sistem Promptu Prensipleri

| Prensip | Uygulama |
|---------|----------|
| **Kanıta dayalı** | Yalnızca sağlanan BAĞLAM bloğundaki kılavuz pasajlarına dayanır |
| **İlaç bilgisi** | Kılavuzda geçen etken maddeler (metotreksat, anti-TNF, anti-IL17, JAK...) açıklanabilir |
| **Klinik sentez** | Dolaylı sorulara bağlamdaki bilgiyi sentezle — hemen "bulunamadı" deme |
| **Bulunamadı eşiği** | Yalnızca kılavuzla hiçbir klinik ilgi yoksa `bulunamadi: true` |
| **Zorunlu atıf** | Her önemli tespitin yanında: `(TR2025, s.12)` |
| **Dil** | Akademik, akıcı, hekim seviyesinde Türkçe |

### JSON Çıktı Şeması

```json
{
  "cevap": "Türkçe klinik açıklama metni. Önemli tespitler için (TR2025, s.34) gibi atıf içerir.",
  "kaynaklar": [
    {
      "kaynak_kodu":    "TR2025",
      "display_source": "Türkiye Psoriasis Tedavi Kılavuzu 2025 (TDD/PSOKİD)",
      "sayfa":          34,
      "bolum":          "Sistemik Tedavi Kriterleri",
      "alinti":         "Kılavuzdan alınan kilit ifade (maks 120 karakter)"
    }
  ],
  "bulunamadi": false
}
```

### Sağlam JSON Parse Katmanı

Gemini bazen Markdown kod bloğu döndürebilir. Sistem dört aşamalı savunma kurar:

```
1. json.loads(raw, strict=False)              → kontrol karakterlerini tolere eder
2. ```json...``` Markdown bloğu               → iç kısmı çıkarır, temiz JSON alınır
3. Regex ile "cevap": alanı ve kaynaklar      → ayrıca parse edilir
4. Ham metni yanıt olarak kabul et            → son çare
```

### Fallback Mekanizması

Gemini API erişilemezse sistem çökmez:

```python
# En iyi chunk'ın metni doğrudan döndürülür
cevap = "(LLM yanıt üretemedi — kılavuz metni doğrudan aktarılıyor)\n\n" + best.text
# fallback_kullanildi: True bayrağı → UI'da uyarı gösterilir
```

---

## Adım 9 — İndeksleme Aracı (`rag/index_cli.py`)

**Amaç:** PDF kaynaklarını parse edip ChromaDB'ye tek seferlik yazmak.

### Kullanım

```bash
# Normal indeksleme (zaten doluysa atlar)
python -m rag.index_cli

# Mevcut DB'yi silerek yeniden indeksle
python -m rag.index_cli --force

# Sadece bir kaynağı indeksle
python -m rag.index_cli --source TR2025

# Mevcut durumu kontrol et
python -m rag.index_cli --check
```

### 4 Aşamalı Pipeline

```
📄 1/4 PDF Metin Çıkarma...
  [TR2025] 312 sayfa işleniyor...
  [EG2025] 231 sayfa işleniyor...
  ⏱  12.4s

✂️  2/4 Metni Chunk'lara Bölme...
  Toplam chunk: 1.147
  ⏱  0.3s

🔢 3/4 Embedding (Gemini gemini-embedding-001)...
  1147 chunk × ~280 kelime ≈ API çağrısı yapılıyor...
  Embedding: 1147/1147 (100%)
  ⏱  ~15 dakika (Free Tier, 2s batch arası bekleme)

💾 4/4 ChromaDB'ye Kaydediliyor...
  Kaydedildi: 1147/1147
  ⏱  2.1s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ İNDEXLEME TAMAMLANDI
  📦 Toplam chunk: 1147
  ⏱  Toplam süre: ~16 dakika
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

> **Not:** İndeksleme yalnızca bir kez çalıştırılır. ChromaDB disk üzerinde kalıcıdır; API her başlatıldığında yalnızca mevcut koleksiyon açılır, yeniden indeksleme yapılmaz.

---

## Adım 10 — FastAPI Entegrasyonu (`api/main.py`)

### Başlangıç — Lazy Loading

```python
# Uygulama başlarken RAG servisleri yüklenir
global rag_retriever, rag_qa

_store = VectorStore()
if _store.chunk_count > 0:
    _embedder     = Embedder()
    rag_retriever = Retriever(_embedder, _store)
    rag_qa        = QAEngine()
    print(f"[RAG] ✅ Hazır — {_store.chunk_count} chunk yüklendi.")
else:
    print("[RAG] ⚠️  ChromaDB henüz indexlenmemiş. Çalıştırın: python -m rag.index_cli")
    # Sistem çalışmaya devam eder; /guideline-query → 503
```

### Yeni Endpoint

```python
@app.post("/guideline-query")
@limiter.limit("10/minute")   # Gemini çağrısı pahalı — dakikada 10 yeterli
async def guideline_query(
    request: Request,
    body: GuidelineQueryRequest,
    current_user: TokenData = Depends(get_current_user),   # JWT zorunlu
):
    ...
```

**İstek:**
```json
{
  "soru": "PASI > 10 olduğunda hangi tedavi basamağına geçilmeli?",
  "kaynak_filtre": ["TR2025"]   // null → her iki kaynak
}
```

**Akış:**
```
JWT doğrulama + rate limit kontrolü
    ↓
rag_retriever.retrieve(soru, kaynak_filtre)  → retrieval_ms ölçümü
    ↓
rag_qa.answer(soru, retrieval, retrieval_ms)
    ↓
qa_response.to_dict()  → JSON yanıt
```

| Endpoint | Method | Auth | Limit | Açıklama |
|----------|--------|------|-------|----------|
| `/guideline-query` | POST | JWT | 10/dak | Kılavuz soru-cevap (RAG) |

---

## Adım 11 — Blazor Arayüzü (`KilavuzDanisan.razor`)

**Sayfa URL:** `/kilavuz-danisan`

### Sayfa Yapısı

```
┌──────────────────────────────────────────────────────────────────┐
│  📚 Klinik Kılavuz Danışmanı                                     │
│  TR2025 (PSOKİD)  ·  EuroGuiDerm 2025  ·  1.100+ taranmış bölüm │
│  [ Tümü ] [ 🇹🇷 TR2025 (PSOKİD) ] [ 🇪🇺 EuroGuiDerm ]          │
├────────────────────────────────┬─────────────────────────────────┤
│  SOHBET PANELİ                 │  KAYNAKLAR PANELİ               │
│                                │                                 │
│  Hızlı Klinik Kartlar:         │  📄 TR2025, s.34                │
│  • PASI eşiği                  │  Sistemik Tedavi Kriterleri     │
│  • Psoriatik artrit            │  Benzerlik: %84                 │
│  • Biyolojik seçim             │  "PASI > 10 veya BSA > %10..."  │
│  • Gebelikte tedavi            │  ─────────────────────────────  │
│  • Nail psoriasis              │  📄 EG2025, s.89               │
│                                │  Biologic Treatment Selection   │
│  ──────────────────────────    │  Benzerlik: %79                 │
│  [ Sorunuzu yazın...     ]     │  "In patients with PASI..."     │
│  [         Danış         ]     │  ─────────────────────────────  │
│                                │  ⏱ 1.240 ms                    │
│                                │  🤖 Gemini 3.5 Flash           │
│                                │  📦 5 chunk tarandı             │
└────────────────────────────────┴─────────────────────────────────┘
```

### UI Özellikleri

- **Sohbet tabanlı:** Soru-yanıt çiftleri kronolojik olarak birikir; bağlam takibi kolaydır
- **Hızlı klinik kartlar:** Sık sorulan senaryolar tek tıkla sorulur — hekim iş akışına uygun
- **Kaynak paneli:** Her yanıt için kılavuz kaynağı, sayfa numarası, bölüm adı ve benzerlik yüzdesi gösterilir
- **Kaynak filtresi:** TR2025, EG2025 veya ikisi birden — sorgu kapsamı hekime bırakılır
- **Sohbet sıfırlama:** Yeni konuşma başlatma butonu
- **Karşılama ekranı:** İlk açılışta boş sohbette kılavuz adları ve hızlı klinik kartlar gösterilir

---

## Adım 12 — Build ve Doğrulama

### İndeks Durumu Kontrolü

```bash
python -m rag.index_cli --check

# Beklenen çıktı:
# 📂 ChromaDB Yolu: .../rag/chroma_db
# ✅ 1147 chunk mevcut — RAG hazır.
```

### API Uçtan Uca Testi

```bash
# 1. Token al
TOKEN=$(curl -sX POST http://localhost:8000/token \
  -d "username=doktor&password=cdss2024&grant_type=password" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Kılavuz sorusu gönder
curl -sX POST http://localhost:8000/guideline-query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"soru": "PASI skoruna göre hastalık şiddeti nasıl sınıflandırılır?"}' \
  | python3 -m json.tool

# Beklenen yanıt:
# {
#   "cevap": "Türkiye Psoriasis Tedavi Kılavuzu 2025'e göre PASI skoru...",
#   "kaynaklar": [{ "kaynak_kodu": "TR2025", "sayfa": 18, ... }],
#   "bulunamadi": false,
#   "islem_suresi_ms": 1240.3
# }
```

---

## Öğrenilen Dersler

1. **Sistem promptu en kritik bileşendir** — Çok gevşek → hallüsinasyon; çok katı → bağlamdaki doğru bilgiler bile söylenmez. Doğru denge: "SADECE bu bağlamdan cevap ver, ama cevabı kendi kelimelerinle yaz."

2. **Distance threshold olmadan RAG işe yaramaz** — Eşik yoksa konu dışı sorulara uydurma yanıt üretilir. `0.75` değeri `found=False` döndürerek LLM'i hiç çağırmaz.

3. **İki farklı embedding task type zorunlu** — `RETRIEVAL_DOCUMENT` (indexleme) ve `RETRIEVAL_QUERY` (sorgulama) Gemini tarafından ayrı optimize edilir; ikisi için aynı task type retrieval doğruluğunu düşürür.

4. **Tek koleksiyon + metadata filtresi** — İki ayrı koleksiyon gereksiz karmaşıklık yaratır. `{"source_code": {"$in": ["TR2025"]}}` ile kaynak kısıtlaması ve çapraz kaynak retrieval aynı anda desteklenir.

5. **pdfplumber font boyutu = başlık tespiti** — Regex veya heuristic yöntemlerin önünde. Kılavuz içinde "Bölüm X" formatı tutarsızsa font büyüklüğü tek güvenilir göstergedir.

6. **Free Tier quota yönetimi** — `batch_size=10`, `delay=2s` ve üstel+kota-duyarlı retry olmadan büyük indeksleme işlemleri 429 hatası ile yarıda kesilir.

7. **Fallback her zaman gerekli** — Gemini API geçici olarak erişilemez olabilir. Ham chunk metnini doğrudan döndüren fallback, kullanıcıya boş ekran yerine kılavuz bilgisi sunar.

---

## Üretilen Dosyalar (Faz 5 — 8 yeni modül)

```
dermatology_project/
├── rag/
│   ├── config.py        ← YENİ: Tüm sabitler (chunk boyutu, eşikler, model adları, kaynaklar)
│   ├── extractor.py     ← YENİ: PDF → temiz PageData (pdfplumber, font-bazlı başlık tespiti)
│   ├── chunker.py       ← YENİ: PageData → örtüşen Chunk listesi (kayan pencere algoritması)
│   ├── embedder.py      ← YENİ: Gemini embedding + retry + rate limit yönetimi
│   ├── store.py         ← YENİ: ChromaDB koleksiyon yönetimi (upsert + cosine query)
│   ├── retriever.py     ← YENİ: Soru → Top-K chunk (threshold + sayfa çeşitliliği)
│   ├── qa_engine.py     ← YENİ: Bağlam + soru → Gemini → JSON yanıt (fallback dahil)
│   ├── index_cli.py     ← YENİ: Tek seferlik indeksleme pipeline'ı (CLI aracı)
│   └── chroma_db/       ← Kalıcı ChromaDB verisi (git'e girmiyor)
│
├── api/main.py                                         ← /guideline-query endpoint'i eklendi
│
└── cdss_web/
    ├── Components/Pages/KilavuzDanisan.razor           ← YENİ: Chat tabanlı kılavuz UI
    └── Services/CdssApiService.cs                      ← GuidelineQueryAsync() eklendi
```

---

## Çalıştırma Komutları

```bash
# 1. İlk kurulum — indeksleme (bir kez çalıştırılır)
source .venv/bin/activate
python -m rag.index_cli

# 2. Terminal 1 — FastAPI Backend
uvicorn api.main:app --reload --port 8000

# 3. Terminal 2 — Blazor Web Arayüzü
cd cdss_web && dotnet run --urls "http://localhost:5000"
```

| Sayfa | URL |
|-------|-----|
| 📚 Kılavuz Danışmanı | http://localhost:5000/kilavuz-danisan |
| 🔬 Hasta Değerlendirme | http://localhost:5000/degerlendirme |
| 📋 Audit Log (admin) | http://localhost:5000/audit-log |
| 📖 FastAPI Docs | http://localhost:8000/docs |

---

## Sistem Sınırları ve Klinik Uyarılar

> **Bu sistem klinik karar destek aracıdır. Ürettiği yanıtlar yalnızca ilgili kılavuz metinlerine dayanır ve bilimsel danışma niteliği taşır. Nihai tedavi kararı her zaman hekime aittir.**

- LLM yanıtı kılavuzda bulunmayan bilgi üretmez — distance threshold + sistem promptu ile önlenir
- ChromaDB indekslenmemişse `/guideline-query` → `503 Service Unavailable`; diğer endpointler etkilenmez
- Gemini Free Tier rate limit'e tabidir; yoğun kullanımda `/guideline-query` geçici `429` dönebilir
- İndeksleme tamamlandıktan sonra ChromaDB disk üzerinde kalıcıdır; API yeniden başlatılırken tekrar indeksleme yapılmaz