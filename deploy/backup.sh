#!/usr/bin/env bash
# Back up the ProcuraFlow database (pg_dump custom format) and the uploaded files, then prune old backups.
#
#   deploy/backup.sh [backup-directory]
#
# Reads POSTGRES_USER, POSTGRES_DB and BACKUP_RETENTION_DAYS from the repository's .env (defaults: procuraflow,
# procuraflow, 14). The default directory is deploy/backups. Needs the stack to be running (docker compose up).
# Example cron entry (daily at 02:15):  15 2 * * * /opt/procuraflow/deploy/backup.sh >> /var/log/procuraflow-backup.log 2>&1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE=(docker compose --env-file "$ROOT_DIR/.env" -f "$SCRIPT_DIR/docker-compose.yml")

if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "error: $ROOT_DIR/.env not found" >&2
    exit 1
fi

# Read single settings without sourcing the whole file (values may contain characters the shell would interpret).
read_env() {
    local value
    value="$(grep -E "^$1=" "$ROOT_DIR/.env" | tail -n 1 | cut -d= -f2- || true)"
    value="${value%$'\r'}"
    printf '%s' "${value:-$2}"
}

DB_USER="$(read_env POSTGRES_USER procuraflow)"
DB_NAME="$(read_env POSTGRES_DB procuraflow)"
RETENTION_DAYS="$(read_env BACKUP_RETENTION_DAYS 14)"
BACKUP_DIR="${1:-$SCRIPT_DIR/backups}"

case "$RETENTION_DAYS" in
    '' | *[!0-9]*) echo "error: BACKUP_RETENTION_DAYS must be a whole number, got '$RETENTION_DAYS'" >&2; exit 1 ;;
esac

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DB_FILE="$BACKUP_DIR/procuraflow-db-$STAMP.dump"
FILES_ARCHIVE="$BACKUP_DIR/procuraflow-uploads-$STAMP.tar.gz"

# Write to a temporary name first so an interrupted run never leaves a file that looks complete.
echo "Dumping database $DB_NAME ..."
"${COMPOSE[@]}" exec -T postgres pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom --no-owner > "$DB_FILE.partial"
if [ ! -s "$DB_FILE.partial" ]; then
    rm -f "$DB_FILE.partial"
    echo "error: pg_dump produced no output" >&2
    exit 1
fi
mv "$DB_FILE.partial" "$DB_FILE"

echo "Archiving uploaded files ..."
"${COMPOSE[@]}" exec -T backend tar -czf - -C /app/var/uploads . > "$FILES_ARCHIVE.partial"
mv "$FILES_ARCHIVE.partial" "$FILES_ARCHIVE"

echo "Pruning backups older than $RETENTION_DAYS days ..."
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'procuraflow-db-*.dump' -o -name 'procuraflow-uploads-*.tar.gz' \) \
    -mtime "+$RETENTION_DAYS" -print -delete

echo "Done:"
echo "  $DB_FILE"
echo "  $FILES_ARCHIVE"
echo "Copy these off the server; a backup on the same disk does not survive losing the disk."
