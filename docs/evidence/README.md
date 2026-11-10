# Evidence to capture before you submit

The acceptance script writes `latest-acceptance.log` here. That file is gitignored because it is generated on your machine. Keep a copy with your submission notes.

Also save:

- The GitHub Actions run URL after you push.
- `docker image inspect` output showing the image id (the acceptance log includes it).
- A screenshot of `/health` and `/ready` through `https://localhost:8443`.
- The conflicting-booking response (`409 seat_conflict`) and the single confirmed PNR.
- Backup file name, the cancelled state, and the restored confirmed state.
- The API container user (`uid=10001`) and the failed `DROP TABLE` from the app role.

Do not commit `.env`, database dumps that contain anything other than demo data, or the generated TLS key.
