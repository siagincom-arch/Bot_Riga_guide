#!/bin/bash
set -e

# Riga Guide KB Restore Script
# Restores Chroma DB and SQLite bot.db from a tar.gz backup
# Creates a safety pre-restore backup

if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_backup.tar.gz>"
    exit 1
fi

BACKUP_FILE="$1"
DATA_DIR="data"
SAFETY_DIR="data/.pre-restore-backup"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "❌ Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

cd "$(dirname "$0")/.." || exit 1

echo "Starting restore from: ${BACKUP_FILE}"

# 1. Provide safety pre-restore backup
if [ -d "${DATA_DIR}" ]; then
    echo "Creating safety backup of current data at ${SAFETY_DIR}..."
    rm -rf "${SAFETY_DIR}"
    mkdir -p "${SAFETY_DIR}"
    # Move current chroma and db to safety dir if they exist
    if [ -d "${DATA_DIR}/chroma" ]; then
        mv "${DATA_DIR}/chroma" "${SAFETY_DIR}/"
    fi
    if [ -f "${DATA_DIR}/bot.db" ]; then
        mv "${DATA_DIR}/bot.db" "${SAFETY_DIR}/"
    fi
    # Also grab bot.db-wal and bot.db-shm if they exist
    if [ -f "${DATA_DIR}/bot.db-wal" ]; then
        mv "${DATA_DIR}/bot.db-wal" "${SAFETY_DIR}/"
    fi
    if [ -f "${DATA_DIR}/bot.db-shm" ]; then
        mv "${DATA_DIR}/bot.db-shm" "${SAFETY_DIR}/"
    fi
fi

# 2. Extract tar.gz directly
# Given that tar was created with data/chroma and data/bot.db
# We can extract directly in the project root, it will overwrite into data/
echo "Extracting backup..."
tar -xzf "${BACKUP_FILE}" -C .

echo "✅ Restore successful."
echo "If something went wrong, safety copies are available in: ${SAFETY_DIR}"
