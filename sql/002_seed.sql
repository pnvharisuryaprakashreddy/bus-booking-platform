-- Resets demo routes, trips and seats. Safe to re-run on the local demo database.
-- Travel dates are always tomorrow, the day after, and the day after that in Asia/Kolkata,
-- so the sample trips do not go stale.

TRUNCATE TABLE bookings, seats, trips, stops, routes RESTART IDENTITY CASCADE;

INSERT INTO routes (code, origin, destination, distance_km) VALUES
    ('VJA-HYD', 'Vijayawada', 'Hyderabad', 275),
    ('HYD-BLR', 'Hyderabad', 'Bengaluru', 570),
    ('DEL-JAI', 'Delhi', 'Jaipur', 280);

INSERT INTO stops (route_id, name, sequence_no)
SELECT id, 'Vijayawada', 1 FROM routes WHERE code = 'VJA-HYD'
UNION ALL
SELECT id, 'Suryapet', 2 FROM routes WHERE code = 'VJA-HYD'
UNION ALL
SELECT id, 'Hyderabad', 3 FROM routes WHERE code = 'VJA-HYD'
UNION ALL
SELECT id, 'Hyderabad', 1 FROM routes WHERE code = 'HYD-BLR'
UNION ALL
SELECT id, 'Kurnool', 2 FROM routes WHERE code = 'HYD-BLR'
UNION ALL
SELECT id, 'Bengaluru', 3 FROM routes WHERE code = 'HYD-BLR'
UNION ALL
SELECT id, 'Delhi', 1 FROM routes WHERE code = 'DEL-JAI'
UNION ALL
SELECT id, 'Gurugram', 2 FROM routes WHERE code = 'DEL-JAI'
UNION ALL
SELECT id, 'Jaipur', 3 FROM routes WHERE code = 'DEL-JAI';

INSERT INTO trips (route_id, bus_number, fare_inr, departure_at, arrival_at)
SELECT
    routes.id,
    'ALG-' || routes.code || '-' || to_char(days.day, 'MMDD'),
    fares.fare,
    (days.day + TIME '21:30') AT TIME ZONE 'Asia/Kolkata',
    ((days.day + TIME '21:30') AT TIME ZONE 'Asia/Kolkata') + INTERVAL '8 hours'
FROM routes
JOIN (
    VALUES
        ('VJA-HYD', 799),
        ('HYD-BLR', 1299),
        ('DEL-JAI', 699)
) AS fares (code, fare) ON fares.code = routes.code
CROSS JOIN (
    SELECT ((CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date + offs) AS day
    FROM generate_series(1, 3) AS offs
) AS days;

INSERT INTO seats (trip_id, seat_number, row_no, column_letter)
SELECT
    trips.id,
    rows.row_no::text || cols.column_letter,
    rows.row_no,
    cols.column_letter
FROM trips
CROSS JOIN generate_series(1, 8) AS rows (row_no)
CROSS JOIN (VALUES ('A'), ('B'), ('C'), ('D')) AS cols (column_letter);
