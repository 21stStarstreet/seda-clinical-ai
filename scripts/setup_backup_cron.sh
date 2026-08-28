#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CDSS Backup Otomasyonu — macOS launchd Kurulum Script'i
# Çalıştırın: bash scripts/setup_backup_cron.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

PLIST_SRC="$(dirname "$0")/com.cdss.backup.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.cdss.backup.plist"

echo "📂 LaunchAgents dizini oluşturuluyor..."
mkdir -p "$HOME/Library/LaunchAgents"

echo "📋 Plist dosyası kopyalanıyor..."
cp "$PLIST_SRC" "$PLIST_DST"

echo "🔄 Servis yükleniyor..."
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo ""
echo "✅ Kurulum tamamlandı!"
echo "   Yedekleme her gece saat 02:00'de otomatik çalışacak."
echo ""
echo "📋 Komutlar:"
echo "   Hemen test et : python scripts/backup.py"
echo "   Durumu gör    : launchctl list | grep cdss"
echo "   Durdur        : launchctl unload ~/Library/LaunchAgents/com.cdss.backup.plist"
echo "   Tekrar başlat : launchctl load ~/Library/LaunchAgents/com.cdss.backup.plist"
echo "   Log izle      : tail -f backup.log"
