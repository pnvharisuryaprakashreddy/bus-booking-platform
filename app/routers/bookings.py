from fastapi import APIRouter, Depends
from psycopg import Connection

from app.config import get_settings
from app.db import get_conn
from app.deps import require_api_key
from app.errors import DomainError
from app.metrics import metrics
from app.schemas import BookingCreate, TicketOut
from app.services.reservations import cancel_booking, create_booking, get_ticket

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=TicketOut, status_code=201)
def create(
    payload: BookingCreate,
    conn: Connection = Depends(get_conn),
    _: None = Depends(require_api_key),
) -> TicketOut:
    try:
        ticket = create_booking(conn, payload, get_settings().tz_name)
    except DomainError as exc:
        if exc.code == "seat_conflict":
            metrics.inc("bookings_conflict_total")
        raise
    metrics.inc("bookings_created_total")
    return ticket


@router.get("/{pnr}", response_model=TicketOut)
def read(pnr: str, conn: Connection = Depends(get_conn)) -> TicketOut:
    return get_ticket(conn, pnr, get_settings().tz_name)


@router.post("/{pnr}/cancel", response_model=TicketOut)
def cancel(
    pnr: str,
    conn: Connection = Depends(get_conn),
    _: None = Depends(require_api_key),
) -> TicketOut:
    ticket = cancel_booking(conn, pnr, get_settings().tz_name)
    metrics.inc("bookings_cancelled_total")
    return ticket
