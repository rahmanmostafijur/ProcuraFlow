#!/usr/bin/env bash
# Restore a ProcuraFlow backup made by deploy/backup.sh. THIS REPLACES THE CURRENT DATABASE CONTENT.
#
#   deploy/restore.sh <database-dump> [uploads-archive] [--yes]
#
# Without --yes you must type the database name to confirm. The API is stopped during the restore and started
# again afterwards. Take a fresh backup first if the current data matters.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE=(docker compose --env-file "$ROOT_DIR/.env" -f "$SCRIPT_DIR/docker-compose.yml")

ASSUME_YES=0
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--yes" ]; then ASSUME_YES=1; else ARGS+=("$arg"); fi
done

if [ "${#ARGS[@]}" -lt 1 ] || [ "${#ARGS[@]}" -gt 2 ]; then
    echo "usage: $0 <database-dump> [uploads-archive] [--yes]" >&2
    exit 2
fi
DB_FILE="${ARGS[0]}"
FILES_ARCHIVE="${ARGS[1]:-}"

[ -f "$ROOT_DIR/.env" ] || { echo "error: $ROOT_DIR/.env not found" >&2; exit 1; }
[ -s "$DB_FILE" ] || { echo "error: dump '$DB_FILE' not found or empty" >&2; exit 1; }
if [ -n "$FILES_ARCHIVE" ] && [ ! -s "$FILES_ARCHIVE" ]; then
    echo "error: uploads archive '$FILES_ARCHIVE' not found or empty" >&2
    exit 1
fi

read_env() {
    local value
    value="$(grep -E "^$1=" "$ROOT_DIR/.env" | tail -n 1 | cut -d= -f2- || true)"
    value="${value%$'\r'}"
    printf '%s' "${value:-$2}"
}
DB_USER="$(read_env POSTGRES_USER procuraflow)"
DB_NAME="$(read_env POSTGRES_DB procuraflow)"

echo "About to REPLACE the contents of database '$DB_NAME' with $DB_FILE"
[ -n "$FILES_ARCHIVE" ] && echo "and REPLACE the uploaded files with $FILES_ARCHIVE"
if [ "$ASSUME_YES" -ne 1 ]; then
    printf "Type the database name (%s) to continue: " "$DB_NAME"
    read -r answer
    if [ "$answer" != "$DB_NAME" ]; then
        echo "Aborted: nothing was changed."
        exit 1
    fi
fi

echo "Stopping the API ..."
"${COMPOSE[@]}" stop backend

echo "Restoring the database ..."
# --clean --if-exists drops each object before recreating it, so the restore also works into a non-empty database.
"${COMPOSE[@]}" exec -T postgres pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner --exit-on-error \
    < "$DB_FILE"

if [ -n "$FILES_ARCHIVE" ]; then
    echo "Restoring uploaded files ..."
    # The backend container is stopped, so run the extraction in a one-off container that mounts the same volume.
    "${COMPOSE[@]}" run --rm --no-deps -T --entrypoint sh backend -c \
        'find /app/var/uploads -mindepth 1 -delete && tar -xzf - -C /app/var/uploads' < "$FILES_ARCHIVE"
fi

echo "Starting the API ..."
"${COMPOSE[@]}" start backend
echo "Restore finished. Sign in and check the data. The API applies any newer migrations when it starts."
