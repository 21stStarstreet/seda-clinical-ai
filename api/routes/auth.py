"""
Kimlik Doğrulama Servisi (Faz 4)
==================================
JWT tabanlı giriş ve çıkış yönetimi.

Öğrenme notu:
- OAuth2PasswordBearer: FastAPI'nin standart token-based auth şeması.
  Tarayıcı "Authorization: Bearer <token>" header'ı ile istek atar.
- JWT (JSON Web Token): İmzalı, küçük bir JSON paketi. İçinde kim olduğun
  (sub), rolün (role) ve ne zaman sona ereceği (exp) yazar.
  Sunucu her istekte bu token'ı doğrular — veritabanına bakmadan!
- bcrypt: Tek yönlü şifre özeti (hash). "cdss2024" → uzun anlamsız metin.
  Geri döndürülemez, sadece karşılaştırma yapılır.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config.settings import settings

router = APIRouter(tags=["Kimlik Doğrulama"])

# ─── Şifre Hashleme ────────────────────────────────────────────────────────────
# bcrypt: endüstri standardı tek-yönlü hash algoritması
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── Token Şeması ──────────────────────────────────────────────────────────────
# tokenUrl: Blazor'un token almak için POST atacağı adres
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# ─── Kullanıcı Veritabanı (Faz 4: Hardcoded → bcrypt hash'li) ─────────────────
# Faz 5'te: Gerçek veritabanına (PostgreSQL + AD/LDAP) bağlanılacak
USERS_DB: dict[str, dict] = {
    "doktor": {
        "username": "doktor",
        "full_name": "Doktor",
        "role": "doktor",
        "hashed_password": "$2b$12$5u2APpPCLCE6QtfQPmaa4udI6inR5w.dSntjli1ueSi0XWYYAR7fK",  # cdss2024
        "disabled": False,
    },
    "mustafa.tiras": {
        "username": "mustafa.tiras",
        "full_name": "Mustafa Tıraş",
        "role": "doktor",
        "hashed_password": "$2b$12$MG/h7Hd3AyLATpj5cv.WhuMpuXuvlpEADHLFHmkZqzvUFmpenpFaC",  # 12345
        "disabled": False,
    },
    "admin": {
        "username": "admin",
        "full_name": "Admin",
        "role": "admin",
        "hashed_password": "$2b$12$wU.q2j2B/.X9C5iJpUrGC.vI2LuRM8Li.btiu.AwEKmTpl5QhTpxq",  # admin2024
        "disabled": False,
    },
}

# ─── Token Kara Listesi (Logout için) ──────────────────────────────────────────
# Öğrenme notu: JWT'ler stateless — sunucu onları "hatırlamaz".
# Çıkış yapıldığında token'ı geçersiz kılmak için kara listeye ekliyoruz.
# In-memory: Sunucu yeniden başlarsa liste temizlenir (geliştirme ortamı için yeterli).
# Üretimde: Redis ile kalıcı kara liste kurulabilir.
revoked_tokens: set[str] = set()


# ─── Pydantic Şemaları ─────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


# ─── Yardımcı Fonksiyonlar ─────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Düz şifre ile bcrypt hash'i karşılaştır."""
    return pwd_context.verify(plain_password, hashed_password)


def get_user(username: str) -> Optional[dict]:
    return USERS_DB.get(username)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Kullanıcı adı ve şifre doğrula. Başarısızsa None döner."""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict) -> str:
    """
    JWT oluştur.
    
    Öğrenme notu:
    to_encode içindeki veriler (sub, role, exp) token içine yazılır.
    Bu veriler şifrelenmez — sadece imzalanır!
    Token'ı decode edebilirsiniz ama değiştiremezsiniz (imza bozulur).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> TokenData:
    """
    Gelen JWT'yi doğrula.
    Kara listede mi, imzası geçerli mi, süresi dolmuş mu kontrol eder.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya süresi dolmuş oturum. Lütfen tekrar giriş yapın.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Kara liste kontrolü
    if token in revoked_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum kapatılmış. Lütfen tekrar giriş yapın.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        role: str = payload.get("role", "doktor")
        if username is None:
            raise credentials_exception
        return TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """FastAPI dependency: Her korumalı endpoint bu fonksiyonu çağırır."""
    return verify_token(token)


def require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Yalnızca admin rolüne izin ver."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gereklidir.",
        )
    return current_user


def require_any_role(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Herhangi bir giriş yapmış kullanıcıya izin ver (admin veya hekim)."""
    return current_user


# ─── Endpoint'ler ──────────────────────────────────────────────────────────────

@router.post("/token", response_model=Token, summary="Giriş yap ve JWT al")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Kullanıcı adı ve şifre ile giriş yap.
    Başarılıysa 8 saatlik geçerli bir JWT döner.
    
    Öğrenme notu:
    OAuth2PasswordRequestForm standart bir form şemasıdır.
    Blazor bu endpoint'e 'username' ve 'password' alanlarıyla form-data POST atar.
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
        "name": user.get("full_name", user["username"]),
    })
    print(f"[Auth] Giriş başarılı: {user['username']} (rol: {user['role']})")

    return Token(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        username=user.get("full_name", user["username"]),
    )


@router.post("/logout", summary="Oturumu sonlandır ve token'ı geçersiz kıl")
async def logout(current_user: TokenData = Depends(get_current_user), token: str = Depends(oauth2_scheme)):
    """
    Mevcut JWT'yi kara listeye ekle.
    
    Öğrenme notu:
    JWT stateless olduğu için 'sil' komutu yoktur.
    Token'ı kara listeye ekleyerek sonraki isteklerde reddedilmesini sağlarız.
    """
    revoked_tokens.add(token)
    print(f"[Auth] Çıkış yapıldı: {current_user.username} — token kara listeye eklendi.")
    return {"message": "Oturum başarıyla sonlandırıldı."}
