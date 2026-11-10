from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from app.config import get_settings
from app.db import get_conn
from app.schemas import RouteOut, SeatMapOut, SeatOut, StopOut, TripOut

router = APIRouter(tags=["catalog"])


@router.get("/routes", response_model=list[RouteOut])
def list_routes(conn: Connection = Depends(get_conn)) -> list[RouteOut]:
    rows = conn.execute(
        """
        SELECT id, code, origin, destination, distance_km
        FROM routes
        ORDER BY code
        """
    ).fetchall()
    return [RouteOut.model_validate(row) for row in rows]


@router.get("/routes/{code}", response_model=RouteOut)
def get_route(code: str, conn: Connection = Depends(get_conn)) -> RouteOut:
    route = conn.execute(
        """
        SELECT id, code, origin, destination, distance_km
        FROM routes
        WHERE code = %s
        """,
        (code,),
    ).fetchone()
    if route is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "route_not_found", "message": f"Route {code} does not exist."},
        )
    stops = conn.execute(
        """
        SELECT id, name, sequence_no
        FROM stops
        WHERE route_id = %s
        ORDER BY sequence_no
        """,
        (route["id"],),
    ).fetchall()
    payload = dict(route)
    payload["stops"] = [StopOut.model_validate(row) for row in stops]
    return RouteOut.model_validate(payload)


@router.get("/trips", response_model=list[TripOut])
def list_trips(
    route_code: str | None = Query(default=None),
    travel_date: date | None = Query(default=None),
    conn: Connection = Depends(get_conn),
) -> list[TripOut]:
    tz = get_settings().tz_name
    rows = conn.execute(
        """
        SELECT
            t.id,
            r.code AS route_code,
            r.origin,
            r.destination,
            t.bus_number,
            t.fare_inr,
            (t.departure_at AT TIME ZONE %s)::date AS travel_date,
            t.departure_at,
            t.arrival_at,
            t.status
        FROM trips t
        JOIN routes r ON r.id = t.route_id
        WHERE (%s::text IS NULL OR r.code = %s)
          AND (%s::date IS NULL OR (t.departure_at AT TIME ZONE %s)::date = %s)
        ORDER BY t.departure_at, t.id
        """,
        (tz, route_code, route_code, travel_date, tz, travel_date),
    ).fetchall()
    return [TripOut.model_validate(row) for row in rows]


@router.get("/trips/{trip_id}", response_model=TripOut)
def get_trip(trip_id: int, conn: Connection = Depends(get_conn)) -> TripOut:
    tz = get_settings().tz_name
    row = conn.execute(
        """
        SELECT
            t.id,
            r.code AS route_code,
            r.origin,
            r.destination,
            t.bus_number,
            t.fare_inr,
            (t.departure_at AT TIME ZONE %s)::date AS travel_date,
            t.departure_at,
            t.arrival_at,
            t.status
        FROM trips t
        JOIN routes r ON r.id = t.route_id
        WHERE t.id = %s
        """,
        (tz, trip_id),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "trip_not_found", "message": f"Trip {trip_id} does not exist."},
        )
    return TripOut.model_validate(row)


@router.get("/trips/{trip_id}/seats", response_model=SeatMapOut)
def seat_map(trip_id: int, conn: Connection = Depends(get_conn)) -> SeatMapOut:
    exists = conn.execute("SELECT 1 FROM trips WHERE id = %s", (trip_id,)).fetchone()
    if exists is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "trip_not_found", "message": f"Trip {trip_id} does not exist."},
        )
    rows = conn.execute(
        """
        SELECT seat_number, row_no, column_letter, status
        FROM seats
        WHERE trip_id = %s
        ORDER BY row_no, column_letter
        """,
        (trip_id,),
    ).fetchall()
    seats = [
        SeatOut(
            seat_number=row["seat_number"],
            row=row["row_no"],
            column=row["column_letter"],
            status=row["status"],
        )
        for row in rows
    ]
    return SeatMapOut(trip_id=trip_id, seats=seats)
