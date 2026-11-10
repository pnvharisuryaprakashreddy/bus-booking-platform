# What to enter on the form

Form: https://forms.gle/fzdSi7nxkbbiwKCs5
Deadline: 15 November 2026, end of day.

| Field | Value |
| --- | --- |
| Full name | P N V Hari Surya Prakash Reddy |
| Registration number | 12300496 |
| University email | The LPU email you use with Career Services. Do not invent one. |
| Internship role | DevOps & Cloud Engineering |
| Assigned project | Cloud Deployment & CI/CD – Bus Booking Platform |
| Primary branch | `main` after you push |
| Technology | Python 3.12, FastAPI, PostgreSQL 16, Docker Compose, Nginx, GitHub Actions |
| Live demo URL | Local only. HTTPS entry is `https://localhost:8443`. |
| Repository, commit, video | Fill these after you create the GitHub repo, push, and record the demo. |

## Evidence the form asks for

- CI run URL: the GitHub Actions run for `.github/workflows/ci.yml` after the push.
- Image tag and id: `bus-booking-api:<git sha>` from the build log, and the local id printed by `./ops/acceptance.sh`.
- Deployment evidence: `docs/evidence/latest-acceptance.log` plus a screenshot of `/health` and `/ready`.
- Architecture: `docs/architecture.svg` and `docs/ARCHITECTURE.md`.
- Backup and rollback: the acceptance log, `docs/RUNBOOK.md`, and the backup file name it prints.
- Domain rule: the `409 seat_conflict` lines in the acceptance log and in pytest.

## Demo video, about 4 minutes

1. Show the assigned project title and this repository.
2. Open the GitHub Actions run: lint, tests, image tag.
3. `curl -k https://localhost:8443/health` and `/ready`.
4. Book seat `7A`, then book it again and show `409` and a single confirmed row.
5. Show `docker compose logs --tail=20 api` with the JSON line.
6. Stop the API, show the proxy returning 502 or 504, start it, show `/ready` again.
7. Point at the backup file and the restored PNR in the acceptance log.

You will also have a 15-minute walkthrough. The seat lock is in `app/services/reservations.py`. The pipeline is `.github/workflows/ci.yml`. Recovery commands are `ops/backup.sh`, `ops/restore.sh` and `ops/rollback.sh`.

## Declarations you can make if they match what you did

- Demo data only. No real passenger data, passwords, or cloud keys are in git.
- `.env.example` is placeholders. `.env` is gitignored.
- You can explain the booking transaction, the Compose network, and the rollback difference between image tag and database restore.

Say that Cursor Grok 4.7 was used to draft the service and the ops files, and that you ran the tests and the local stack yourself. The form asks for AI tools and what they were used for.
