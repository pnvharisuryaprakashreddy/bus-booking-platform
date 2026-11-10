from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class Passenger(BaseModel):
    name: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z][A-Za-z .'-]*$")
    age: int = Field(ge=1, le=120)
    gender: Gender
    phone: str = Field(pattern=r"^[6-9][0-9]{9}$")
    email: EmailStr


class BookingCreate(BaseModel):
    trip_id: int = Field(gt=0)
    seat_number: str = Field(pattern=r"^[1-8][ABCD]$")
    travel_date: date
    boarding_stop_id: int = Field(gt=0)
    drop_stop_id: int = Field(gt=0)
    passenger: Passenger


class StopOut(BaseModel):
    id: int
    name: str
    sequence_no: int


class RouteOut(BaseModel):
    id: int
    code: str
    origin: str
    destination: str
    distance_km: int
    stops: list[StopOut] = []


class TripOut(BaseModel):
    id: int
    route_code: str
    origin: str
    destination: str
    bus_number: str
    fare_inr: int
    travel_date: date
    departure_at: datetime
    arrival_at: datetime
    status: str


class SeatOut(BaseModel):
    seat_number: str
    row: int
    column: str
    status: str


class SeatMapOut(BaseModel):
    trip_id: int
    seats: list[SeatOut]


class TicketOut(BaseModel):
    pnr: str
    status: str
    trip_id: int
    route_code: str
    origin: str
    destination: str
    bus_number: str
    seat_number: str
    fare_inr: int
    travel_date: date
    departure_at: datetime
    arrival_at: datetime
    boarding_stop: str
    drop_stop: str
    passenger_name: str
    passenger_age: int
    passenger_gender: str
    passenger_phone: str
    passenger_email: str
    created_at: datetime
    cancelled_at: datetime | None = None


class HealthOut(BaseModel):
    status: str
    service: str
    version: str


class ReadyOut(BaseModel):
    status: str
    routes: int
