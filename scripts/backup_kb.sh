#!/bin/bash
set -e

# Riga Guide KB Backup Script
# Creates a compressed archive of Chroma DB and SQLite bot.db
# Deletes backups older than 14 days

# Config
DATA_DIR="data"
BACKUP_DIR="backups"
DATE=$(date +"%Y-%m-%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/kb_backup_${DATE}.tar.gz"
RETENTION_DAYS=14

# Change to project root (assume script is running from scripts/ or project root)
cd "$(dirname "$0")/.." || exit 1

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

echo "Starting backup to ${BACKUP_FILE}..."

# Check if data exists
if [ ! -d "${DATA_DIR}/chroma" ] && [ ! -f "${DATA_DIR}/bot.db" ]; then
    echo "Warning: No KB data found in ${DATA_DIR}. Nothing to backup."
    exit 0
fi

# Create tar archive
# Will backup both if they exist. Use -C to strip data prefix if we wanted to, but simpler to preserve paths.
tar -czf "${BACKUP_FILE}" "${DATA_DIR}/chroma" "${DATA_DIR}/bot.db" 2>/dev/null || true

if [ -f "${BACKUP_FILE}" ]; then
    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "✅ Backup successful: ${BACKUP_FILE} (Size: ${SIZE})"
else
    echo "❌ Backup failed."
    exit 1
fi

# Cleanup old backups
echo "Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "kb_backup_*.tar.gz" -type f -mtime +${RETENTION_DAYS} -delete
echo "Cleanup done."
