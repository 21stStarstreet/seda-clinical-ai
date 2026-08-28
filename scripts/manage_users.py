#!/usr/bin/env python3
"""
CDSS Kullanıcı Yönetim Aracı
=============================
Sistemin auth.py dosyasındaki USERS_DB'ye kullanıcı ekler, listeler ve siler.

Kullanım:
    python scripts/manage_users.py list
    python scripts/manage_users.py add <kullanici_adi> <sifre> <rol>
    python scripts/manage_users.py remove <kullanici_adi>
    python scripts/manage_users.py passwd <kullanici_adi> <yeni_sifre>

Roller:
    doktor  — Hasta değerlendirme ve geçmiş kararlar
    admin   — Tüm yetkiler

Örnek:
    python scripts/manage_users.py add dr.ayse cdss2025 doktor
    python scripts/manage_users.py add admin2 guclu_sifre admin
    python scripts/manage_users.py passwd doktor yeni_sifre123
    python scripts/manage_users.py remove dr.ayse

UYARI:
    Bu script auth.py dosyasını DOĞRUDAN DÜZENLER.
    Değişiklikler için API'yi yeniden başlatmanız gerekir: uvicorn api.main:app --reload
"""

import sys
import re
from pathlib import Path
from passlib.context import CryptContext

# ─── Yapılandırma ─────────────────────────────────────────────────────────────
AUTH_FILE = Path(__file__).parent.parent / "api" / "routes" / "auth.py"
VALID_ROLES = {"doktor", "admin"}
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

RENKLER = {
    "yesil":  "\033[92m",
    "kirmizi": "\033[91m",
    "sari":   "\033[93m",
    "mavi":   "\033[94m",
    "reset":  "\033[0m",
    "kalin":  "\033[1m",
}


def renkli(metin: str, renk: str) -> str:
    return f"{RENKLER[renk]}{metin}{RENKLER['reset']}"


def auth_dosyasini_oku() -> str:
    if not AUTH_FILE.exists():
        print(renkli(f"HATA: {AUTH_FILE} bulunamadı.", "kirmizi"))
        sys.exit(1)
    return AUTH_FILE.read_text(encoding="utf-8")


def auth_dosyasina_yaz(icerik: str) -> None:
    AUTH_FILE.write_text(icerik, encoding="utf-8")
    print(renkli(f"✓ {AUTH_FILE} güncellendi.", "yesil"))


def kullanicilari_listele():
    """Mevcut tüm kullanıcıları tabloya yaz."""
    icerik = auth_dosyasini_oku()

    # USERS_DB sözlüğünü düzenli ifadeyle çıkar
    kullanici_blok = re.findall(
        r'"(\w+)"\s*:\s*\{[^}]*"role"\s*:\s*"(\w+)"[^}]*"disabled"\s*:\s*(\w+)',
        icerik
    )

    if not kullanici_blok:
        print(renkli("Hiç kullanıcı bulunamadı.", "sari"))
        return

    print(f"\n{renkli('Mevcut Kullanıcılar', 'kalin')}")
    print("─" * 40)
    print(f"{'Kullanıcı Adı':<20} {'Rol':<10} {'Durum'}")
    print("─" * 40)
    for ad, rol, disabled in kullanici_blok:
        durum = renkli("Aktif", "yesil") if disabled == "False" else renkli("Devre Dışı", "kirmizi")
        rol_renk = "mavi" if rol == "admin" else "reset"
        print(f"{ad:<20} {renkli(rol, rol_renk):<10} {durum}")
    print("─" * 40)
    print(renkli("\nNOT: Değişiklikler için API'yi yeniden başlatın.", "sari"))


def kullanici_ekle(kullanici_adi: str, sifre: str, rol: str):
    """Yeni kullanıcı ekle."""
    if rol not in VALID_ROLES:
        print(renkli(f"HATA: Geçersiz rol '{rol}'. Geçerli roller: {', '.join(VALID_ROLES)}", "kirmizi"))
        sys.exit(1)

    if len(sifre) < 8:
        print(renkli("HATA: Şifre en az 8 karakter olmalıdır.", "kirmizi"))
        sys.exit(1)

    icerik = auth_dosyasini_oku()

    # Kullanıcı zaten var mı?
    if f'"{kullanici_adi}"' in icerik:
        print(renkli(f"HATA: '{kullanici_adi}' kullanıcısı zaten mevcut.", "kirmizi"))
        sys.exit(1)

    # Şifreyi hashle
    hashli_sifre = pwd_context.hash(sifre)
    print(f"Şifre hashleniyor... {renkli('Tamam', 'yesil')}")

    # Yeni kullanıcı bloğunu hazırla
    yeni_kullanici = f'''    "{kullanici_adi}": {{
        "username": "{kullanici_adi}",
        "role": "{rol}",
        # bcrypt hash of '{sifre[:3]}{"*" * (len(sifre) - 3)}'
        "hashed_password": "{hashli_sifre}",
        "disabled": False,
    }},'''

    # USERS_DB'nin kapanış kısmından önce ekle
    yeni_icerik = icerik.replace(
        "}\n\n# ─── Token Kara Listesi",
        f"}}\n{yeni_kullanici}\n}}\n\n# ─── Token Kara Listesi",
        1
    )

    if yeni_icerik == icerik:
        # Alternatif pattern
        yeni_icerik = icerik.replace(
            "}\n}\n\n# ─── Token Kara Listesi",
            f"}}\n}}\n{yeni_kullanici[4:]}\n}}\n\n# ─── Token Kara Listesi",
            1
        )

    auth_dosyasina_yaz(yeni_icerik)
    print(renkli(f"✓ '{kullanici_adi}' ({rol}) başarıyla eklendi!", "yesil"))
    print(renkli("⚠  API'yi yeniden başlatmayı unutmayın!", "sari"))


def kullanici_sil(kullanici_adi: str):
    """Kullanıcıyı kaldır."""
    if kullanici_adi in ("admin", "doktor"):
        print(renkli(f"HATA: '{kullanici_adi}' varsayılan sistem kullanıcısı silinemez.", "kirmizi"))
        sys.exit(1)

    icerik = auth_dosyasini_oku()

    if f'"{kullanici_adi}"' not in icerik:
        print(renkli(f"HATA: '{kullanici_adi}' kullanıcısı bulunamadı.", "kirmizi"))
        sys.exit(1)

    # Kullanıcı bloğunu düzenli ifadeyle kaldır
    pattern = rf'\s+"{re.escape(kullanici_adi)}"\s*:\s*\{{[^}}]*\}},?'
    yeni_icerik = re.sub(pattern, "", icerik)

    auth_dosyasina_yaz(yeni_icerik)
    print(renkli(f"✓ '{kullanici_adi}' başarıyla silindi!", "yesil"))
    print(renkli("⚠  API'yi yeniden başlatmayı unutmayın!", "sari"))


def sifre_degistir(kullanici_adi: str, yeni_sifre: str):
    """Kullanıcının şifresini değiştir."""
    if len(yeni_sifre) < 8:
        print(renkli("HATA: Şifre en az 8 karakter olmalıdır.", "kirmizi"))
        sys.exit(1)

    icerik = auth_dosyasini_oku()

    if f'"{kullanici_adi}"' not in icerik:
        print(renkli(f"HATA: '{kullanici_adi}' kullanıcısı bulunamadı.", "kirmizi"))
        sys.exit(1)

    yeni_hash = pwd_context.hash(yeni_sifre)

    # Kullanıcıya ait hashed_password satırını bul ve değiştir
    # Önce kullanıcı bloğunu bul, sonra sadece o bloktaki hash'i değiştir
    kullanici_pattern = rf'("{re.escape(kullanici_adi)}"\s*:\s*\{{[^}}]*?"hashed_password"\s*:\s*)"[^"]*"'
    yeni_icerik = re.sub(kullanici_pattern, rf'\1"{yeni_hash}"', icerik)

    if yeni_icerik == icerik:
        print(renkli("HATA: Şifre alanı bulunamadı veya güncellenemedi.", "kirmizi"))
        sys.exit(1)

    auth_dosyasina_yaz(yeni_icerik)
    print(renkli(f"✓ '{kullanici_adi}' şifresi başarıyla değiştirildi!", "yesil"))
    print(renkli("⚠  API'yi yeniden başlatmayı unutmayın!", "sari"))


def yardim_goster():
    print(f"""
{renkli('CDSS Kullanıcı Yönetim Aracı', 'kalin')}

{renkli('Komutlar:', 'mavi')}
  python scripts/manage_users.py list
      Tüm kullanıcıları listele

  python scripts/manage_users.py add <kullanici_adi> <sifre> <rol>
      Yeni kullanıcı ekle (roller: doktor, admin)
      Örn: python scripts/manage_users.py add dr.ayse cdss2025 doktor

  python scripts/manage_users.py remove <kullanici_adi>
      Kullanıcıyı sil (admin ve doktor silinemez)

  python scripts/manage_users.py passwd <kullanici_adi> <yeni_sifre>
      Kullanıcının şifresini değiştir

{renkli('Not:', 'sari')} Her değişiklikten sonra uvicorn'u yeniden başlatın.
""")


# ─── Ana Program ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        yardim_goster()
        sys.exit(0)

    komut = sys.argv[1].lower()

    if komut == "list":
        kullanicilari_listele()

    elif komut == "add":
        if len(sys.argv) != 5:
            print(renkli("Kullanım: manage_users.py add <kullanici_adi> <sifre> <rol>", "kirmizi"))
            sys.exit(1)
        kullanici_ekle(sys.argv[2], sys.argv[3], sys.argv[4])

    elif komut == "remove":
        if len(sys.argv) != 3:
            print(renkli("Kullanım: manage_users.py remove <kullanici_adi>", "kirmizi"))
            sys.exit(1)
        kullanici_sil(sys.argv[2])

    elif komut == "passwd":
        if len(sys.argv) != 4:
            print(renkli("Kullanım: manage_users.py passwd <kullanici_adi> <yeni_sifre>", "kirmizi"))
            sys.exit(1)
        sifre_degistir(sys.argv[2], sys.argv[3])

    else:
        print(renkli(f"Bilinmeyen komut: '{komut}'", "kirmizi"))
        yardim_goster()
        sys.exit(1)
