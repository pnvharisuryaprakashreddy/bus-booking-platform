# Bus trip and seat reservation API

**Student:** P N V Hari Surya Prakash Reddy
**Registration number:** 12300496
**Role:** DevOps & Cloud Engineering
**Assigned project:** Cloud Deployment & CI/CD – Bus Booking Platform
**Submission form:** https://forms.gle/fzdSi7nxkbbiwKCs5
**Deadline:** 15 November 2026, end of day

This is the allocated service only: routes, trips, a seat map, booking creation and cancellation. It is built so a clean machine can build it, start it, see health and logs, reject a duplicate seat, and restore a backup.

## Stack

- Python 3.12, FastAPI, Uvicorn
- PostgreSQL 16
- Docker Compose for the API, database and Nginx
- GitHub Actions for ruff, pytest, a commit-tagged image and a Trivy scan

## Prerequisites

Docker Desktop, Python 3.12, and git. Copy the placeholder env file before the first start:

```bash
cp .env.example .env
```

Do not commit `.env`. The values in the example are local placeholders.

## Run

```bash
docker compose up -d --build
curl -k https://localhost:8443/health
curl -k https://localhost:8443/ready
```

Interactive API docs are at `https://localhost:8443/docs`. The certificate is self-signed and is generated inside the proxy container. It is not a public certificate and it is not committed.

`/health` reports the image version. A Compose build of tag `local` returns `"version": "local"`.

## Port map

| Port | Who can reach it | What it is |
| --- | --- | --- |
| 8443 | your machine, and the LAN if the firewall allows | HTTPS via Nginx |
| 8080 | same | HTTP redirect to HTTPS port 8443 |
| 8000 | localhost only | API process |
| 5433 | localhost only | Postgres. Host port 5433 avoids a local server already using 5432. Inside Compose the database is still `db:5432`. |

## Environment variables

| Variable | Used by | Purpose |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | database container | superuser password, used for backup and restore |
| `BUSAPP_PASSWORD` | database init | password for the application role |
| `DATABASE_URL` | API | connection string for role `busapp` |
| `API_KEY` | API | required header `X-API-Key` on create and cancel |
| `APP_VERSION` / `IMAGE_TAG` | API image | value returned by `/health` |
| `LOG_LEVEL` | API | Python log level |
| `TZ_NAME` | API | travel-date comparison timezone, default `Asia/Kolkata` |

## Book a seat

```bash
curl -k https://localhost:8443/routes/VJA-HYD
curl -k "https://localhost:8443/trips?route_code=VJA-HYD"
```

Copy `id`, `travel_date` and the stop ids from those responses. Boarding must be an earlier stop than the drop. The numbers below are the shape of the request; if they do not match the live trip, the API correctly returns 422.

```bash
curl -k -X POST https://localhost:8443/bookings \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-api-key' \
  -d '{
    "trip_id": 1,
    "seat_number": "1A",
    "travel_date": "YYYY-MM-DD",
    "boarding_stop_id": 1,
    "drop_stop_id": 3,
    "passenger": {
      "name": "Demo Passenger",
      "age": 22,
      "gender": "male",
      "phone": "9876543210",
      "email": "demo@example.com"
    }
  }'
```

Sending that request a second time for the same trip and seat returns `409` and `seat_conflict`. The second call does not create a PNR. Two concurrent requests are covered by `tests/test_api.py`: the seat row is locked with `SELECT ... FOR UPDATE`, and a partial unique index rejects a second confirmed row.

Cancel with:

```bash
curl -k -X POST https://localhost:8443/bookings/BBSXXXXXXX/cancel \
  -H 'X-API-Key: dev-api-key'
```

Seeded routes are Vijayawada–Hyderabad, Hyderabad–Bengaluru and Delhi–Jaipur. Each route has trips on the next three days, departing 21:30 Asia/Kolkata, with seats `1A`–`8D`.

## Tests and lint

Start the stack once so `busbooking_test` exists, then:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
make lint
make test
```

`make test` uses database `busbooking_test` on `127.0.0.1:5433`. The tests refuse to run if the database name does not end in `_test`.

## CI

`.github/workflows/ci.yml` runs on push and pull request to `main` or `master`:

1. `ruff check`, `ruff format --check`, and `pip-audit`
2. `pytest` against a Postgres service
3. `docker build` tagged `bus-booking-api:<full git sha>`, then a Trivy report

The pipeline does not need repository secrets. After you push, the run URL is the CI evidence for the form.

## Backup, restore and rollback

```bash
./ops/backup.sh
./ops/restore.sh backups/busbooking-<timestamp>.sql
./ops/rollback.sh local
```

Restore stops the API while the dump is loaded, then starts it. Rollback only changes the image tag. It does not rewind table rows. Details and the failure drill are in [docs/RUNBOOK.md](docs/RUNBOOK.md).

```bash
./ops/acceptance.sh
```

This books a seat, proves the duplicate is rejected, restores a backup, stops the API, and starts it again. The log is `docs/evidence/latest-acceptance.log`.

## Layout

| Path | Why it is there |
| --- | --- |
| `app/services/reservations.py` | Booking transaction and the duplicate-seat rule |
| `sql/` | Schema, unique index, seed data |
| `Dockerfile` | Non-root image |
| `docker-compose.yml` | API, Postgres, Nginx, volume, health checks |
| `ops/nginx/` | TLS proxy |
| `ops/backup.sh`, `ops/restore.sh`, `ops/rollback.sh` | Recovery commands |
| `.github/workflows/ci.yml` | Lint, test, image, scan |
| `docs/ARCHITECTURE.md` | Diagram and trust boundaries |
| `docs/RUNBOOK.md` | Deploy, logs, backup, incidents |

## Known limits

- TLS is a local self-signed certificate, not Let's Encrypt or a cloud load balancer.
- One API container. The seat lock is still correct with more workers because it lives in Postgres.
- `/metrics` is a simple counter page, not a Prometheus server.
- No passenger login and no payments. The brief asks for this API, not the full booking product.
- Base images are version tags (`python:3.12-slim-bookworm`, `postgres:16-alpine`, `nginx:1.27-alpine`), not pinned digests.
- CI builds the image on the runner. It does not push to a registry.

## Attribution

The service, Compose files, workflow and docs in this repository were drafted with Cursor Grok 4.7, then checked by running the tests and the local stack. Demo passengers use `demo@example.com` and phone `9876543210`. No real customer data is included.
