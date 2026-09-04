-- Create slots table
CREATE TABLE IF NOT EXISTS slots (
    id SERIAL PRIMARY KEY,
    center TEXT NOT NULL,
    crop TEXT NOT NULL,
    time TEXT NOT NULL,
    max_capacity INTEGER NOT NULL
);

-- Create procurement_plans table
CREATE TABLE IF NOT EXISTS procurement_plans (
    id SERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    center_id INTEGER NOT NULL,
    center_name TEXT NOT NULL,
    category TEXT NOT NULL,
    limit_tons REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, center_id)
);

-- Create bookings table
CREATE TABLE IF NOT EXISTS bookings (
    token TEXT PRIMARY KEY,
    farmer_name TEXT NOT NULL,
    farmer_id TEXT NOT NULL,
    center_id INTEGER,
    center_name TEXT,
    slot_id INTEGER,
    crop TEXT NOT NULL,
    quantity_quintals REAL DEFAULT 0.0,
    quantity_tons REAL DEFAULT 0.0,
    time_slot TEXT NOT NULL,
    sub_queue_id TEXT NOT NULL,
    booking_date TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default slots (only if the table is empty)
INSERT INTO slots (id, center, crop, time, max_capacity) 
VALUES 
    (1, 'Center 1 - North Cereals Hub', 'Cereals', '09:00 AM - 11:00 AM', 50),
    (2, 'Center 1 - North Cereals Hub', 'Cereals', '11:00 AM - 01:00 PM', 50),
    (3, 'Center 1 - North Cereals Hub', 'Cereals', '02:00 PM - 04:00 PM', 50),
    (4, 'Center 1 - North Cereals Hub', 'Cereals', '04:00 PM - 06:00 PM', 50),
    (5, 'Center 3 - East Pulse Depot', 'Pulses', '09:00 AM - 11:00 AM', 50),
    (6, 'Center 3 - East Pulse Depot', 'Pulses', '11:00 AM - 01:00 PM', 50),
    (7, 'Center 3 - East Pulse Depot', 'Pulses', '02:00 PM - 04:00 PM', 50),
    (8, 'Center 3 - East Pulse Depot', 'Pulses', '04:00 PM - 06:00 PM', 50)
ON CONFLICT (id) DO NOTHING;

-- Reset sequence for slots since we inserted specific IDs
SELECT setval(pg_get_serial_sequence('slots', 'id'), coalesce(max(id),0) + 1, false) FROM slots;
