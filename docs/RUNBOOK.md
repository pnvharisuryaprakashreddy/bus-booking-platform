# Operations runbook

Commands assume the repository root and a local `.env` copied from `.env.example`.

## Deploy

```bash
cp .env.example .env
docker compose up -d --build
curl -k https://localhost:8443/ready
```

The first database start loads `sql/001_schema.sql` and `sql/002_seed.sql`. Repeating `docker compose up` does not reload seed data. To rebuild the demo data from scratch:

```bash
docker compose down -v
docker compose up -d --build
```

`-v` deletes the Postgres volume.

## Port map

| Port | Bind | Service |
| --- | --- | --- |
| 8443 | all interfaces | Nginx HTTPS, the public entry |
| 8080 | all interfaces | Nginx HTTP, redirects to `https://<host>:8443` |
| 8000 | 127.0.0.1 only | API, for local debugging |
| 5433 | 127.0.0.1 only | Postgres, for tests and `psql`. Mapped off 5432 so it does not collide with another local database. |

## Restart

```bash
docker compose restart api
docker compose ps
docker compose logs --tail=100 api
```

`restart: unless-stopped` is set on the API, database and proxy, so a container crash comes back without a new command. `docker compose stop api` stays stopped until `docker compose start api`.

## Logs

```bash
docker compose logs -f --tail=100 api
docker compose logs --tail=50 proxy
docker compose logs --tail=50 db
```

API lines are JSON. A normal booking has `msg` `booking_created` and fields `pnr`, `trip_id`, `seat_number`. A rejected duplicate has `domain_error` with `error` `seat_conflict`.

## Health and readiness

- `GET /health` answers when the process is up. It does not check the database. Use it as the container liveness check.
- `GET /ready` runs `SELECT COUNT(*) FROM routes` and returns 503 when the database is unreachable or the seed is missing. Nginx starts only after this check passes. Use it to decide whether the service can take bookings.

## Backup

```bash
./ops/backup.sh
```

This runs `pg_dump` as the database superuser inside the `db` container and writes `backups/busbooking-<utc timestamp>.sql`.

## Restore

```bash
./ops/restore.sh backups/busbooking-<timestamp>.sql
```

The script stops the API, loads the dump, and starts the API again. Check a known PNR afterwards:

```bash
curl -k https://localhost:8443/ready
curl -k https://localhost:8443/bookings/<PNR>
```

## Rollback

Images are tagged `bus-booking-api:<git sha>` in CI and `bus-booking-api:local` by Compose.

```bash
docker image ls bus-booking-api
./ops/rollback.sh <previous-tag>
```

Rollback changes the running image. It does not restore database rows. Use the restore procedure for data. Confirm `/health` shows the version you rolled back to. The Compose build arg writes that tag into `APP_VERSION`.

## Failure drill

```bash
docker compose stop api
curl -k -o /dev/null -w '%{http_code}\n' https://localhost:8443/ready
docker compose start api
curl -k https://localhost:8443/ready
```

The stopped API should surface as HTTP 502 or 504 from Nginx, or as a connection error. This stack returns 504 when the proxy's connect timeout expires. Readiness returns 200 after the start. Bookings survive because they are in the Postgres volume, not in the API container.

`./ops/acceptance.sh` performs this drill, plus a conflicting booking, a backup, a restore and the privilege check.

## Incident response

| What you see | What it means | What to do |
| --- | --- | --- |
| Proxy returns 502 | API process is down or still starting | `docker compose ps`, then `docker compose logs --tail=100 api`. Start or restart `api`. |
| `/health` is 200 and `/ready` is 503 | Process is up, database is not usable | `docker compose ps db` and `docker compose logs --tail=100 db`. If the volume was recreated without seed, run the schema and seed SQL. |
| `409 seat_conflict` | The seat is already confirmed for that trip | Not an outage. The other request kept the only PNR. |
| `401` on POST | Missing or wrong `X-API-Key` | Compare the header with `API_KEY` in `.env`. Do not print the key into logs or the ticket. |
| Disk full on the Docker volume | Backups or Postgres cannot write | Remove old files in `backups/`, then `docker system df`. |

## Least privilege check

```bash
docker compose exec -T -e PGPASSWORD=busapp_local_only db \
  psql -U busapp -d busbooking -c 'DROP TABLE routes;'
```

This must fail. The application role does not own the tables. Use the password from your `.env` if you changed it.
