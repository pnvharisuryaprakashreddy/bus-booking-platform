#!/bin/sh
# First-boot database setup. Postgres runs this only when the data volume is empty.
set -eu

if [ -z "${BUSAPP_PASSWORD:-}" ]; then
    echo "BUSAPP_PASSWORD is required" >&2
    exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /sql/001_schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /sql/002_seed.sql

exists=$(psql -tA --username "$POSTGRES_USER" --dbname postgres -c "SELECT 1 FROM pg_database WHERE datname = 'busbooking_test'")
if [ "$exists" != "1" ]; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE busbooking_test"
fi

escaped=$(printf '%s' "$BUSAPP_PASSWORD" | sed "s/'/''/g")

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'busapp') THEN
        CREATE ROLE busapp LOGIN PASSWORD '${escaped}';
    ELSE
        ALTER ROLE busapp WITH LOGIN PASSWORD '${escaped}';
    END IF;
END
\$\$;

GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO busapp;
GRANT CONNECT ON DATABASE busbooking_test TO busapp;
GRANT USAGE ON SCHEMA public TO busapp;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO busapp;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO busapp;
SQL

echo "Database ${POSTGRES_DB} is ready. Application role busapp has DML only."
