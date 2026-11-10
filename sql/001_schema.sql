-- Drops and recreates the reservation tables.
-- Used for a first database init and for the isolated busbooking_test database.
-- Do not run this against a database you need to keep. Restore backups instead.

DROP TABLE IF EXISTS bookings CASCADE;
DROP TABLE IF EXISTS seats CASCADE;
DROP TABLE IF EXISTS trips CASCADE;
DROP TABLE IF EXISTS stops CASCADE;
DROP TABLE IF EXISTS routes CASCADE;

CREATE TABLE routes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    distance_km INTEGER NOT NULL CHECK (distance_km > 0)
);

CREATE TABLE stops (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    route_id BIGINT NOT NULL REFERENCES routes (id),
    name TEXT NOT NULL,
    sequence_no INTEGER NOT NULL CHECK (sequence_no > 0),
    UNIQUE (route_id, sequence_no),
    UNIQUE (route_id, name)
);

CREATE TABLE trips (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    route_id BIGINT NOT NULL REFERENCES routes (id),
    bus_number TEXT NOT NULL,
    fare_inr INTEGER NOT NULL CHECK (fare_inr > 0),
    departure_at TIMESTAMPTZ NOT NULL,
    arrival_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'cancelled')),
    CHECK (arrival_at > departure_at)
);

CREATE INDEX trips_route_departure_idx ON trips (route_id, departure_at);

CREATE TABLE seats (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_id BIGINT NOT NULL REFERENCES trips (id),
    seat_number TEXT NOT NULL,
    row_no INTEGER NOT NULL CHECK (row_no BETWEEN 1 AND 8),
    column_letter TEXT NOT NULL CHECK (column_letter IN ('A', 'B', 'C', 'D')),
    status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'booked')),
    UNIQUE (trip_id, seat_number)
);

CREATE TABLE bookings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pnr TEXT NOT NULL UNIQUE,
    trip_id BIGINT NOT NULL REFERENCES trips (id),
    seat_id BIGINT NOT NULL REFERENCES seats (id),
    passenger_name TEXT NOT NULL,
    passenger_age INTEGER NOT NULL CHECK (passenger_age BETWEEN 1 AND 120),
    passenger_gender TEXT NOT NULL CHECK (passenger_gender IN ('male', 'female', 'other')),
    passenger_phone TEXT NOT NULL,
    passenger_email TEXT NOT NULL,
    boarding_stop_id BIGINT NOT NULL REFERENCES stops (id),
    drop_stop_id BIGINT NOT NULL REFERENCES stops (id),
    status TEXT NOT NULL CHECK (status IN ('confirmed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelled_at TIMESTAMPTZ,
    CHECK (boarding_stop_id <> drop_stop_id)
);

-- Backstop for the concurrent-booking rule. Cancelled rows stay for history
-- and do not block a later booking of the same seat.
CREATE UNIQUE INDEX bookings_one_confirmed_seat
    ON bookings (trip_id, seat_id)
    WHERE status = 'confirmed';
