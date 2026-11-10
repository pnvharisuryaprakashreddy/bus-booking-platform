import logging
import secrets
from datetime import date

from psycopg import Connection
from psycopg.errors import UniqueViolation

from app.errors import DomainError
from app.schemas import BookingCreate, TicketOut

logger = logging.getLogger("app.reservations")

_PNR_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_pnr() -> str:
    suffix = "".join(secrets.choice(_PNR_ALPHABET) for _ in range(7))
    return f"BBS{suffix}"


def _ticket_from_row(row: dict) -> TicketOut:
    return TicketOut.model_validate(row)


_TICKET_SQL = """
SELECT
    b.pnr,
    b.status,
    b.passenger_name,
    b.passenger_age,
    b.passenger_gender,
    b.passenger_phone,
    b.passenger_email,
    b.created_at,
    b.cancelled_at,
    t.id AS trip_id,
    t.bus_number,
    t.fare_inr,
    t.departure_at,
    t.arrival_at,
    (t.departure_at AT TIME ZONE %s)::date AS travel_date,
    r.code AS route_code,
    r.origin,
    r.destination,
    s.seat_number,
    bs.name AS boarding_stop,
    ds.name AS drop_stop
FROM bookings b
JOIN trips t ON t.id = b.trip_id
JOIN routes r ON r.id = t.route_id
JOIN seats s ON s.id = b.seat_id
JOIN stops bs ON bs.id = b.boarding_stop_id
JOIN stops ds ON ds.id = b.drop_stop_id
WHERE b.pnr = %s
"""


def get_ticket(conn: Connection, pnr: str, tz: str) -> TicketOut:
    row = conn.execute(_TICKET_SQL, (tz, pnr)).fetchone()
    if row is None:
        raise DomainError(404, "pnr_not_found", f"No booking exists for PNR {pnr}.")
    return _ticket_from_row(row)


def create_booking(conn: Connection, data: BookingCreate, tz: str) -> TicketOut:
    """Reserve one seat.

    The seat row is locked with SELECT ... FOR UPDATE so two concurrent requests
    for the same seat cannot both observe it as available. The partial unique
    index on confirmed bookings is the database backstop if a lock is ever skipped.
    """
    for _ in range(5):
        pnr = _new_pnr()
        try:
            with conn.transaction():
                _reserve_locked_seat(conn, data, tz, pnr)
            logger.info(
                "booking_created",
                extra={
                    "extra_fields": {
                        "pnr": pnr,
                        "trip_id": data.trip_id,
                        "seat_number": data.seat_number,
                    }
                },
            )
            return get_ticket(conn, pnr, tz)
        except UniqueViolation as exc:
            constraint = exc.diag.constraint_name if exc.diag else ""
            if constraint == "bookings_pnr_key":
                continue
            raise DomainError(
                409,
                "seat_conflict",
                f"Seat {data.seat_number} is already reserved for this trip.",
            ) from exc
    raise DomainError(500, "pnr_generation_failed", "Could not allocate a unique PNR.")


def _reserve_locked_seat(conn: Connection, data: BookingCreate, tz: str, pnr: str) -> None:
    trip = conn.execute(
        """
        SELECT
            t.id,
            t.route_id,
            t.status,
            (t.departure_at AT TIME ZONE %s)::date AS travel_date
        FROM trips t
        WHERE t.id = %s
        """,
        (tz, data.trip_id),
    ).fetchone()
    if trip is None:
        raise DomainError(404, "trip_not_found", f"Trip {data.trip_id} does not exist.")
    if trip["status"] != "scheduled":
        raise DomainError(422, "trip_not_scheduled", "This trip is not open for booking.")

    today: date = conn.execute(
        "SELECT (CURRENT_TIMESTAMP AT TIME ZONE %s)::date AS today",
        (tz,),
    ).fetchone()["today"]
    if data.travel_date < today:
        raise DomainError(422, "travel_date_in_past", "Travel date cannot be in the past.")
    if data.travel_date != trip["travel_date"]:
        raise DomainError(
            422,
            "travel_date_mismatch",
            "Travel date does not match this trip's departure date.",
        )

    stops = conn.execute(
        """
        SELECT id, name, sequence_no
        FROM stops
        WHERE route_id = %s
        """,
        (trip["route_id"],),
    ).fetchall()
    by_id = {row["id"]: row for row in stops}
    boarding = by_id.get(data.boarding_stop_id)
    drop = by_id.get(data.drop_stop_id)
    if boarding is None or drop is None:
        raise DomainError(
            422,
            "stop_not_on_route",
            "Boarding and drop stops must belong to this trip's route.",
        )
    if boarding["sequence_no"] >= drop["sequence_no"]:
        raise DomainError(
            422,
            "invalid_stop_order",
            "Boarding stop must come before the drop stop.",
        )

    seat = conn.execute(
        """
        SELECT id, status
        FROM seats
        WHERE trip_id = %s AND seat_number = %s
        FOR UPDATE
        """,
        (data.trip_id, data.seat_number),
    ).fetchone()
    if seat is None:
        raise DomainError(
            404,
            "seat_not_found",
            f"Seat {data.seat_number} does not exist on this trip.",
        )
    if seat["status"] != "available":
        raise DomainError(
            409,
            "seat_conflict",
            f"Seat {data.seat_number} is already reserved for this trip.",
        )

    passenger = data.passenger
    conn.execute(
        """
        INSERT INTO bookings (
            pnr, trip_id, seat_id, passenger_name, passenger_age, passenger_gender,
            passenger_phone, passenger_email, boarding_stop_id, drop_stop_id, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'confirmed')
        """,
        (
            pnr,
            data.trip_id,
            seat["id"],
            passenger.name,
            passenger.age,
            passenger.gender.value,
            passenger.phone,
            str(passenger.email),
            data.boarding_stop_id,
            data.drop_stop_id,
        ),
    )
    conn.execute("UPDATE seats SET status = 'booked' WHERE id = %s", (seat["id"],))


def cancel_booking(conn: Connection, pnr: str, tz: str) -> TicketOut:
    with conn.transaction():
        booking = conn.execute(
            """
            SELECT id, status, seat_id
            FROM bookings
            WHERE pnr = %s
            FOR UPDATE
            """,
            (pnr,),
        ).fetchone()
        if booking is None:
            raise DomainError(404, "pnr_not_found", f"No booking exists for PNR {pnr}.")
        if booking["status"] != "confirmed":
            raise DomainError(409, "already_cancelled", f"PNR {pnr} is already cancelled.")
        conn.execute(
            """
            UPDATE bookings
            SET status = 'cancelled', cancelled_at = now()
            WHERE id = %s
            """,
            (booking["id"],),
        )
        conn.execute(
            "UPDATE seats SET status = 'available' WHERE id = %s",
            (booking["seat_id"],),
        )
    logger.info("booking_cancelled", extra={"extra_fields": {"pnr": pnr}})
    return get_ticket(conn, pnr, tz)
