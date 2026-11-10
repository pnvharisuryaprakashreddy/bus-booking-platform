import threading
from datetime import date

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.errors import DomainError
from app.schemas import BookingCreate
from app.services.reservations import create_booking

HEADERS = {"X-API-Key": "test-key"}


def _trip_and_stops(client: TestClient, route_code: str = "VJA-HYD") -> tuple[dict, list[dict]]:
    route = client.get(f"/routes/{route_code}")
    assert route.status_code == 200, route.text
    trips = client.get("/trips", params={"route_code": route_code})
    assert trips.status_code == 200, trips.text
    assert trips.json(), "expected seeded trips"
    return trips.json()[0], route.json()["stops"]


def _payload(trip: dict, stops: list[dict], seat: str = "1A", **overrides: object) -> dict:
    body: dict[str, object] = {
        "trip_id": trip["id"],
        "seat_number": seat,
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
    body.update(overrides)
    return body


def _confirmed_count(database_url: str, trip_id: int, seat_number: str) -> int:
    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM bookings b
            JOIN seats s ON s.id = b.seat_id
            WHERE b.trip_id = %s
              AND s.seat_number = %s
              AND b.status = 'confirmed'
            """,
            (trip_id, seat_number),
        ).fetchone()
    assert row is not None
    return int(row["n"])


def test_health_ready_and_metrics(client: TestClient, reset_db: None) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["version"] == "test"
    assert health.headers["x-request-id"]

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["routes"] >= 3

    client.get("/health")
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text


def test_catalog_and_seat_map(client: TestClient, reset_db: None) -> None:
    routes = client.get("/routes")
    assert routes.status_code == 200
    codes = {row["code"] for row in routes.json()}
    assert codes == {"VJA-HYD", "HYD-BLR", "DEL-JAI"}

    trip, _stops = _trip_and_stops(client)
    seats = client.get(f"/trips/{trip['id']}/seats")
    assert seats.status_code == 200
    body = seats.json()
    assert len(body["seats"]) == 32
    assert {seat["status"] for seat in body["seats"]} == {"available"}

    missing = client.get("/trips/999999")
    assert missing.status_code == 404


def test_booking_conflict_does_not_create_a_second_pnr(
    client: TestClient, reset_db: None, database_url: str
) -> None:
    trip, stops = _trip_and_stops(client)
    first = client.post("/bookings", headers=HEADERS, json=_payload(trip, stops, "1A"))
    assert first.status_code == 201, first.text
    pnr = first.json()["pnr"]
    assert pnr.startswith("BBS")
    assert first.json()["status"] == "confirmed"
    assert first.json()["seat_number"] == "1A"
    assert first.json()["boarding_stop"] == "Vijayawada"
    assert first.json()["drop_stop"] == "Hyderabad"

    second = client.post("/bookings", headers=HEADERS, json=_payload(trip, stops, "1A"))
    assert second.status_code == 409
    assert second.json()["error"] == "seat_conflict"
    assert "pnr" not in second.json()
    assert _confirmed_count(database_url, trip["id"], "1A") == 1

    fetched = client.get(f"/bookings/{pnr}")
    assert fetched.status_code == 200
    assert fetched.json()["pnr"] == pnr

    seat_map = client.get(f"/trips/{trip['id']}/seats").json()
    booked = next(seat for seat in seat_map["seats"] if seat["seat_number"] == "1A")
    assert booked["status"] == "booked"


def test_concurrent_requests_confirm_only_one_seat(
    client: TestClient, reset_db: None, database_url: str
) -> None:
    trip, stops = _trip_and_stops(client, "DEL-JAI")
    payload = BookingCreate.model_validate(_payload(trip, stops, "4B"))
    barrier = threading.Barrier(2)
    results: list[tuple[str, str]] = []

    def worker() -> None:
        barrier.wait(timeout=5)
        with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as conn:
            try:
                ticket = create_booking(conn, payload, "Asia/Kolkata")
                results.append(("ok", ticket.pnr))
            except DomainError as exc:
                results.append(("err", exc.code))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(kind for kind, _code in results) == ["err", "ok"]
    assert any(code == "seat_conflict" for kind, code in results if kind == "err")
    assert _confirmed_count(database_url, trip["id"], "4B") == 1


def test_validation_rules(client: TestClient, reset_db: None) -> None:
    trip, stops = _trip_and_stops(client)
    other = client.get("/routes/DEL-JAI").json()["stops"]

    past = client.post(
        "/bookings",
        headers=HEADERS,
        json=_payload(trip, stops, "2A", travel_date="2020-01-01"),
    )
    assert past.status_code == 422
    assert past.json()["error"] == "travel_date_in_past"

    mismatch = client.post(
        "/bookings",
        headers=HEADERS,
        json=_payload(trip, stops, "2A", travel_date="2099-01-01"),
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"] == "travel_date_mismatch"

    wrong_order = client.post(
        "/bookings",
        headers=HEADERS,
        json=_payload(
            trip,
            stops,
            "2A",
            boarding_stop_id=stops[-1]["id"],
            drop_stop_id=stops[0]["id"],
        ),
    )
    assert wrong_order.status_code == 422
    assert wrong_order.json()["error"] == "invalid_stop_order"

    foreign_stop = client.post(
        "/bookings",
        headers=HEADERS,
        json=_payload(trip, stops, "2A", drop_stop_id=other[-1]["id"]),
    )
    assert foreign_stop.status_code == 422
    assert foreign_stop.json()["error"] == "stop_not_on_route"

    bad_phone = _payload(trip, stops, "2A")
    bad_phone["passenger"]["phone"] = "12345"
    invalid = client.post("/bookings", headers=HEADERS, json=bad_phone)
    assert invalid.status_code == 422
    assert invalid.json()["error"] == "validation_error"

    missing_key = client.post("/bookings", json=_payload(trip, stops, "3C"))
    assert missing_key.status_code == 401


def test_cancel_frees_the_seat_and_second_cancel_fails(
    client: TestClient, reset_db: None, database_url: str
) -> None:
    trip, stops = _trip_and_stops(client, "HYD-BLR")
    created = client.post("/bookings", headers=HEADERS, json=_payload(trip, stops, "5D"))
    assert created.status_code == 201, created.text
    pnr = created.json()["pnr"]

    cancelled = client.post(f"/bookings/{pnr}/cancel", headers=HEADERS)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancelled_at"] is not None
    assert _confirmed_count(database_url, trip["id"], "5D") == 0

    again = client.post("/bookings", headers=HEADERS, json=_payload(trip, stops, "5D"))
    assert again.status_code == 201, again.text
    assert again.json()["pnr"] != pnr
    assert _confirmed_count(database_url, trip["id"], "5D") == 1

    second_cancel = client.post(f"/bookings/{pnr}/cancel", headers=HEADERS)
    assert second_cancel.status_code == 409
    assert second_cancel.json()["error"] == "already_cancelled"

    missing = client.get("/bookings/BBSDOESNOTEXIST")
    assert missing.status_code == 404


@pytest.mark.parametrize("seat", ["9A", "1E", "A1"])
def test_bad_seat_numbers_are_rejected(client: TestClient, reset_db: None, seat: str) -> None:
    trip, stops = _trip_and_stops(client)
    response = client.post("/bookings", headers=HEADERS, json=_payload(trip, stops, seat))
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_missing_trip_returns_404(client: TestClient, reset_db: None) -> None:
    _trip, stops = _trip_and_stops(client)
    response = client.post(
        "/bookings",
        headers=HEADERS,
        json=_payload({"id": 999999, "travel_date": date.today().isoformat()}, stops, "1A"),
    )
    assert response.status_code == 404
    assert response.json()["error"] == "trip_not_found"
