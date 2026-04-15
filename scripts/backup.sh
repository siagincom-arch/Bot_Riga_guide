#!/usr/bin/env bash
# ============================================================
# Riga Guide Bot — Nightly backup script
#
# M10.1 — AG task (AG4.1).
# ARCHITECTURE §3.3: rsync data/ → backups/YYYY-MM-DD/, prune > 7 days.
#
# Запуск через cron на хосте:
#   0 3 * * *  cd /opt/riga-guide && ./scripts/backup.sh
# ============================================================

set -euo pipefail

# --- Конфигурация ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="${PROJECT_DIR}/backups"
TODAY="$(date +%Y-%m-%d)"
BACKUP_DIR="${BACKUP_ROOT}/${TODAY}"
RETENTION_DAYS=7

# --- Проверка наличия данных ---
DATA_DIR="${PROJECT_DIR}/data"
if [ ! -d "$DATA_DIR" ]; then
    echo "[backup] SKIP: data/ directory not found at ${DATA_DIR}"
    exit 0
fi

# --- Создание директории бэкапа ---
mkdir -p "$BACKUP_DIR"

echo "[backup] Starting backup to ${BACKUP_DIR}"

# --- Копируем Chroma (директория) ---
if [ -d "${DATA_DIR}/chroma" ]; then
    rsync -a --delete "${DATA_DIR}/chroma/" "${BACKUP_DIR}/chroma/"
    echo "[backup] chroma/ — OK"
else
    echo "[backup] chroma/ — SKIP (not found)"
fi

# --- Копируем SQLite (файл) ---
if [ -f "${DATA_DIR}/bot.db" ]; then
    cp "${DATA_DIR}/bot.db" "${BACKUP_DIR}/bot.db"
    echo "[backup] bot.db — OK"
else
    echo "[backup] bot.db — SKIP (not found)"
fi

# --- Prune: удаляем бэкапы старше RETENTION_DAYS дней ---
echo "[backup] Pruning backups older than ${RETENTION_DAYS} days..."
PRUNED=0
if [ -d "$BACKUP_ROOT" ]; then
    find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -mtime +${RETENTION_DAYS} | while read -r old_dir; do
        echo "[backup] Removing old backup: ${old_dir}"
        rm -rf "$old_dir"
        PRUNED=$((PRUNED + 1))
    done
fi

echo "[backup] Done. Backup saved to ${BACKUP_DIR}"
