#!/bin/sh
# Writes a logical backup of the demo database. Prints the file path.
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="backups/busbooking-${stamp}.sql"
docker compose exec -T db pg_dump -U postgres -d busbooking --clean --if-exists > "$out"
echo "$out"
