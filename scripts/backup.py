#!/usr/bin/env python3
"""
Faz 4: Otomatik Veritabanı Yedekleme Scripti
============================================
Bu script SQLite veritabanı dosyasını (audit.db) güvenli bir şekilde yedekler.
Yedekler 'backup/' dizinine tarih damgasıyla kopyalanır.
30 günden eski yedekler otomatik olarak silinir.

Cron job olarak çalıştırılması önerilir (ör: her gece 02:00):
0 2 * * * cd /path/to/project && python3 scripts/backup.py
"""

import os
import shutil
import time
from datetime import datetime, timedelta

# Konfigürasyon
DB_FILE = "audit.db"
BACKUP_DIR = "backup"
RETENTION_DAYS = 30
LOG_FILE = "backup.log"

def log_msg(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    with open(LOG_FILE, "a") as f:
        f.write(full_msg + "\n")

def backup_database():
    if not os.path.exists(DB_FILE):
        log_msg(f"HATA: Kaynak veritabanı dosyası bulunamadı ({DB_FILE})")
        return

    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        log_msg(f"Yedek dizini oluşturuldu: {BACKUP_DIR}")

    # Dosya adını tarihle damgala
    date_str = datetime.now().strftime("%Y-%m-%d")
    backup_filename = f"audit_{date_str}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    try:
        # SQLite db dosyasını kopyala
        shutil.copy2(DB_FILE, backup_path)
        
        # Boyut kontrolü
        size_mb = os.path.getsize(backup_path) / (1024 * 1024)
        log_msg(f"BAŞARILI: Yedek alındı -> {backup_path} ({size_mb:.2f} MB)")
    except Exception as e:
        log_msg(f"HATA: Yedek kopyalanırken bir sorun oluştu: {str(e)}")

def cleanup_old_backups():
    if not os.path.exists(BACKUP_DIR):
        return

    now = time.time()
    cutoff_time = now - (RETENTION_DAYS * 86400)
    deleted_count = 0

    for filename in os.listdir(BACKUP_DIR):
        if filename.startswith("audit_") and filename.endswith(".db"):
            filepath = os.path.join(BACKUP_DIR, filename)
            # Dosya oluşturulma/değiştirilme zamanına göre sil
            if os.path.getmtime(filepath) < cutoff_time:
                try:
                    os.remove(filepath)
                    log_msg(f"SİLİNDİ: Eski yedek dosyası kaldırıldı -> {filename}")
                    deleted_count += 1
                except Exception as e:
                    log_msg(f"HATA: {filename} silinemedi: {str(e)}")
    
    if deleted_count == 0:
        log_msg("SİLİNEN YOK: 30 günden eski yedek bulunamadı.")

if __name__ == "__main__":
    log_msg("--- Yedekleme İşlemi Başladı ---")
    backup_database()
    cleanup_old_backups()
    log_msg("--- Yedekleme İşlemi Tamamlandı ---\n")
