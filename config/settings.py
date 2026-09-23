"""
Uygulama genelinde ayarlar.
Tüm konfigürasyon buradan okunur — sihirli sayılar bu dosyaya gömülmez.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from typing import Any
import os
import random
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ─── Temel ───────────────────────────────────────────────────────────────
    random_seed: int = Field(default=42, description="Global deterministik seed")
    model_version: str = Field(default="v3.1", description="Aktif model versiyonu (just for info)")
    model_dir: str = Field(
        default="models/artifacts/production",
        description=(
            "Model klasörü. API her zaman bu dizinin altındaki 'production' alt klasörünü yükler. "
            "Versiyonu değiştirmek için: cp -r models/artifacts/v2.0/* models/artifacts/production/"
        )
    )

    # ─── API ──────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_debug: bool = Field(default=False)

    # ─── Veritabanı ───────────────────────────────────────────────
    database_url: str = Field(default="sqlite:///./audit.db")

    # ─── LLM ──────────────────────────────────────────────────────
    gemini_api_key: str = Field(default="", description="Gemini API anahtarı")
    llm_model: str = Field(default="gemini-3.6-flash", description="Gemini LLM model adı")
    llm_enabled: bool = Field(default=True)
    llm_temperature: float = Field(default=0.1)
    llm_max_tokens: int = Field(default=2000)

    # ─── Faz 4: Güvenlik ──────────────────────────────────────────────
    # JWT — Her ortam için özel, rastgele 256-bit anahtar
    jwt_secret_key: str = Field(
        default="DEV_SECRET_KEY_CHANGE_ME",
        description="JWT imzalama anahtarı. .env dosyasından okunur — asla kaynak koduna girmemeli!"
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_hours: int = Field(default=8, description="Token geçerlilik süresi (saat)")

    # Veritabanı şifreleme — Fernet/AES-128 anahtarı
    encryption_key: str = Field(
        default="DUMMY_KEY_32_BYTES_FOR_DEV_DUMMY_KEY_32=",
        description="Fernet şifreleme anahtarı. .env dosyasından okunur — değiştirilirse eski veriler okunamaz!"
    )

    # CORS — İzin verilen origin'ler (virgillü liste)
    allowed_origins: str = Field(
        default="http://localhost:5000,http://localhost:5001,http://localhost:5285,https://localhost:7256",
        description="Blazor uygulamalarının adresleri. * yasak!"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @model_validator(mode="after")
    def validate_security_keys(self) -> "Settings":
        """
        Varsayılan / sahte güvenlik anahtarlarıyla production'da başlatmayı engeller.
        """
        _INSECURE_JWT = "DEV_SECRET_KEY_CHANGE_ME"
        _INSECURE_FERNET = "DUMMY_KEY_32_BYTES_FOR_DEV_DUMMY_KEY_32="

        is_dev = os.getenv("SEDA_ENV", "development").lower() == "development"

        if self.jwt_secret_key == _INSECURE_JWT:
            if is_dev:
                logger.warning(
                    "[GÜVENLİK] JWT secret key varsayılan değerle çalışıyor! "
                    "Production için .env dosyasına güçlü bir JWT_SECRET_KEY atayın."
                )
            else:
                raise ValueError(
                    "Production ortamında varsayılan JWT_SECRET_KEY kullanılamaz. "
                    ".env dosyasında JWT_SECRET_KEY tanımlayın."
                )

        if self.encryption_key == _INSECURE_FERNET:
            if is_dev:
                logger.warning(
                    "[GÜVENLİK] Fernet şifreleme anahtarı varsayılan değerle çalışıyor! "
                    "Production için .env dosyasına geçerli bir ENCRYPTION_KEY atayın."
                )
            else:
                raise ValueError(
                    "Production ortamında varsayılan ENCRYPTION_KEY kullanılamaz. "
                    ".env dosyasında ENCRYPTION_KEY tanımlayın."
                )

        return self


# ─── Klinik Eşik Değerleri ────────────────────────────────────────────────────
class ClinicalThresholds:
    """
    Kural motoru ve feature engineering için klinik eşik değerleri.
    Doktor onayı olmadan değiştirme!
    """
    VKI_OBEZ: float = 30.0
    VKI_ASIRI_OBEZ: float = 35.0
    LDL_YUKSEK: float = 130.0       # mg/dL
    LDL_COK_YUKSEK: float = 160.0   # mg/dL
    PASI_HAFIF_UST: float = 5.0
    PASI_ORTA_UST: float = 10.0     # Bu değer üzeri → Sistemik Tedavi
    DLQI_YUKSEK: float = 10.0       # 0–30 skala
    BSA_GENIS: float = 10.0         # % vücut yüzey alanı
    GENC_HASTA: float = 40.0        # yaş sınırı


# ─── Label Tanımlamaları ──────────────────────────────────────────────────────
LABEL_NAMES = ["ftr", "aile_hekimligi", "sistemik_tedavi"]

LABEL_DISPLAY_NAMES = {
    "ftr": "Fizik Tedavi ve Rehabilitasyon (FTR)",
    "aile_hekimligi": "Aile Hekimliği",
    "sistemik_tedavi": "Sistemik Tedavi",
}

# ─── Singleton ────────────────────────────────────────────────────────────────
settings = Settings()
thresholds = ClinicalThresholds()


def set_global_seed(seed: int = settings.random_seed) -> None:
    """
    Deterministik çıktı garantisi için global seed ayarla.
    Uygulama başlangıcında bir kez çağrılmalı.
    """
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    os.environ["OMP_NUM_THREADS"] = "1"  # XGBoost thread stabilitesi
