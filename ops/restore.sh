#!/bin/sh
# Restores a backup created by ops/backup.sh into the running database.
set -eu
file=${1:?usage: ops/restore.sh backups/busbooking-YYYYMMDDTHHMMSSZ.sql}
cd "$(dirname "$0")/.."
if [ ! -f "$file" ]; then
    echo "Backup file not found: $file" >&2
    exit 1
fi
# Stop the API so open connections do not block DROP statements in the dump.
docker compose stop api
sleep 2
docker compose exec -T db psql -U postgres -d busbooking -v ON_ERROR_STOP=1 < "$file"
docker compose start api
echo "restored $file"
