#!/usr/bin/env python3
"""Acceptance evidence for the local deployment.

Expects `docker compose up -d --build` to already be running and .env to exist.
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "evidence" / "latest-acceptance.log"
BASE = os.environ.get("BASE_URL", "https://localhost:8443")


def load_env(path: Path) -> None:
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def log(message: str) -> None:
    print(message)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def request(
    method: str,
    path: str,
    body: dict | None = None,
    timeout: int = 10,
) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    api_key = os.environ.get("API_KEY", "")
    if api_key:
        req.add_header("X-API-Key", api_key)
    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, context=context, timeout=timeout) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def wait_ready() -> None:
    last = "no response"
    for _ in range(40):
        try:
            status, payload = request("GET", "/ready")
        except Exception as exc:  # noqa: BLE001 - surface the last connection error
            last = str(exc)
            time.sleep(2)
            continue
        last = f"{status} {payload}"
        if status == 200:
            log(f"PASS ready {payload}")
            return
        time.sleep(2)
    raise SystemExit(f"FAIL readiness did not succeed: {last}")


def psql(sql: str) -> str:
    result = run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "busbooking",
            "-tAc",
            sql,
        ]
    )
    return result.stdout.strip()


def main() -> None:
    load_env(ROOT / ".env")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("", encoding="utf-8")
    log(f"base_url={BASE}")

    wait_ready()
    status, health = request("GET", "/health")
    log(f"PASS health status={status} body={health}")

    status, route = request("GET", "/routes/VJA-HYD")
    if status != 200:
        raise SystemExit(f"FAIL route lookup {status} {route}")
    stops = route["stops"]
    status, trips = request("GET", "/trips?route_code=VJA-HYD")
    if status != 200 or not trips:
        raise SystemExit(f"FAIL trip lookup {status} {trips}")
    trip = trips[0]
    booking = {
        "trip_id": trip["id"],
        "seat_number": "7A",
        "travel_date": trip["travel_date"],
        "boarding_stop_id": stops[0]["id"],
        "drop_stop_id": stops[-1]["id"],
        "passenger": {
            "name": "Demo Passenger",
            "age": 22,
            "gender": "male",
            "phone": "9876543210",
            "email": "demo@example.com",
        },
    }
    status, ticket = request("POST", "/bookings", booking)
    if status != 201:
        raise SystemExit(f"FAIL create booking {status} {ticket}")
    pnr = ticket["pnr"]
    log(f"PASS booking pnr={pnr} seat={ticket['seat_number']} route={ticket['route_code']}")

    status, conflict = request("POST", "/bookings", booking)
    if status != 409 or conflict.get("error") != "seat_conflict":
        raise SystemExit(f"FAIL conflict {status} {conflict}")
    confirmed = psql(
        "SELECT COUNT(*) FROM bookings b "
        "JOIN seats s ON s.id = b.seat_id "
        f"WHERE b.trip_id = {int(trip['id'])} AND s.seat_number = '7A' AND b.status = 'confirmed'"
    )
    if confirmed != "1":
        raise SystemExit(f"FAIL expected 1 confirmed booking, found {confirmed}")
    log(f"PASS conflict status=409 confirmed_rows={confirmed} body={conflict}")

    backup = run(["./ops/backup.sh"])
    backup_path = backup.stdout.strip().splitlines()[-1]
    log(f"PASS backup file={backup_path}")

    status, cancelled = request("POST", f"/bookings/{pnr}/cancel")
    if status != 200 or cancelled.get("status") != "cancelled":
        raise SystemExit(f"FAIL cancel {status} {cancelled}")
    log(f"PASS cancelled pnr={pnr} before restore")

    run(["./ops/restore.sh", backup_path])
    wait_ready()
    status, restored = request("GET", f"/bookings/{pnr}")
    if status != 200 or restored.get("status") != "confirmed":
        raise SystemExit(f"FAIL restore {status} {restored}")
    log(f"PASS restore pnr={pnr} status={restored['status']}")

    identity = run(["docker", "compose", "exec", "-T", "api", "id"])
    if "uid=10001" not in identity.stdout:
        raise SystemExit(f"FAIL api user is not uid 10001: {identity.stdout.strip()}")
    log(f"PASS api user {identity.stdout.strip()}")

    password = os.environ["BUSAPP_PASSWORD"]
    drop = run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            f"PGPASSWORD={password}",
            "db",
            "psql",
            "-U",
            "busapp",
            "-d",
            "busbooking",
            "-c",
            "DROP TABLE routes;",
        ],
        check=False,
    )
    if drop.returncode == 0:
        raise SystemExit("FAIL busapp was able to drop a table")
    log("PASS busapp cannot drop tables")
    log(drop.stderr.strip() or drop.stdout.strip())

    run(["docker", "compose", "stop", "api"])
    time.sleep(2)
    detected = False
    try:
        status, payload = request("GET", "/ready", timeout=5)
        detected = status >= 500
        log(f"PASS failure detected status={status} body={payload}")
    except Exception as exc:  # noqa: BLE001
        detected = True
        log(f"PASS failure detected error={exc}")
    if not detected:
        raise SystemExit("FAIL stopping the API did not fail the proxy check")

    run(["docker", "compose", "start", "api"])
    wait_ready()
    log("PASS api recovered after restart")

    image = run(
        [
            "docker",
            "image",
            "inspect",
            "bus-booking-api:local",
            "--format",
            "{{.Id}}",
        ]
    )
    log(f"PASS image_tag=bus-booking-api:local image_id={image.stdout.strip()}")
    log("PASS acceptance complete")


if __name__ == "__main__":
    main()
