import random
import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AgroProcure Unified API (SQLite Engine)")

DB_FILE = "agroprocure.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # actually enforce the FOREIGN KEY constraint below
    return conn


# Initialize SQLite Database Tables
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Create Slots Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY,
            center TEXT NOT NULL,
            crop TEXT NOT NULL,
            time TEXT NOT NULL,
            max_capacity INTEGER NOT NULL
        )
    """)

    # Create Bookings Table (crop now stored directly, not just via slot lookup)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            token TEXT PRIMARY KEY,
            farmer_name TEXT NOT NULL,
            farmer_id TEXT NOT NULL,
            slot_id INTEGER NOT NULL,
            crop TEXT NOT NULL,
            sub_queue_id TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (slot_id) REFERENCES slots (id)
        )
    """)

    # Populate Initial Static Slots if empty
    cursor.execute("SELECT COUNT(*) FROM slots")
    if cursor.fetchone()[0] == 0:
        initial_slots = [
            (1, "Center A", "Cereals", "09:00 AM - 11:00 AM", 10),
            (2, "Center A", "Cereals", "11:00 AM - 01:00 PM", 10),
            (3, "Center A", "Cereals", "02:00 PM - 04:00 PM", 10),
            (4, "Center A", "Cereals", "04:00 PM - 06:00 PM", 10),
            (5, "Center B", "Pulses", "09:00 AM - 11:00 AM", 10),
            (6, "Center B", "Pulses", "11:00 AM - 01:00 PM", 10),
            (7, "Center B", "Pulses", "02:00 PM - 04:00 PM", 10),
            (8, "Center B", "Pulses", "04:00 PM - 06:00 PM", 10),
        ]
        cursor.executemany(
            "INSERT INTO slots (id, center, crop, time, max_capacity) VALUES (?, ?, ?, ?, ?)",
            initial_slots,
        )

    conn.commit()
    conn.close()


init_db()


class BookingRequest(BaseModel):
    farmer_name: str
    farmer_id: str
    slot_id: int


def generate_unique_token(cursor):
    while True:
        token = str(random.randint(100000, 999999))
        cursor.execute("SELECT token FROM bookings WHERE token = ?", (token,))
        if not cursor.fetchone():
            return token


# 1. GET SLOTS
@app.get("/slots")
def get_slots():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM slots")
    slots = cursor.fetchall()

    slots_response = []
    for slot in slots:
        cursor.execute("SELECT COUNT(*) FROM bookings WHERE slot_id = ?", (slot["id"],))
        booked_count = cursor.fetchone()[0]
        slots_left = slot["max_capacity"] - booked_count

        slots_response.append({
            "id": slot["id"],
            "center": slot["center"],
            "crop": slot["crop"],
            "time": slot["time"],
            "max_capacity": slot["max_capacity"],
            "remaining": slots_left,
        })

    conn.close()
    return {"slots": slots_response}


# 2. CREATE BOOKING
@app.post("/book")
def create_booking(request: BookingRequest):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM slots WHERE id = ?", (request.slot_id,))
    target_slot = cursor.fetchone()
    if not target_slot:
        conn.close()
        raise HTTPException(status_code=404, detail="Slot not found")

    cursor.execute("SELECT COUNT(*) FROM bookings WHERE slot_id = ?", (request.slot_id,))
    booked_count = cursor.fetchone()[0]

    if booked_count >= target_slot["max_capacity"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Slot is full")

    sub_slot_num = booked_count + 1
    sub_queue_id = f"SLOT{target_slot['id']}-{sub_slot_num:02d}"
    token = generate_unique_token(cursor)

    cursor.execute(
        """
        INSERT INTO bookings (token, farmer_name, farmer_id, slot_id, crop, sub_queue_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            token,
            request.farmer_name,
            request.farmer_id,
            request.slot_id,
            target_slot["crop"],
            sub_queue_id,
            "BOOKED",
        ),
    )

    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "token": token,
        "sub_queue_id": sub_queue_id,
        "center": target_slot["center"],
        "time": target_slot["time"],
        "message": "Slot booked successfully!",
    }


# 3. VERIFY TOKEN
@app.post("/verify/{token}")
def verify_token(token: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bookings WHERE token = ?", (token,))
    target_booking = cursor.fetchone()

    if not target_booking:
        conn.close()
        raise HTTPException(status_code=404, detail="Invalid token code")

    if target_booking["status"] == "ARRIVED":
        conn.close()
        raise HTTPException(status_code=400, detail="This token has already been used to check in")

    cursor.execute("UPDATE bookings SET status = 'ARRIVED' WHERE token = ?", (token,))
    conn.commit()

    cursor.execute("SELECT * FROM slots WHERE id = ?", (target_booking["slot_id"],))
    matching_slot = cursor.fetchone()

    conn.close()

    return {
        "status": "VERIFIED",
        "farmer_name": target_booking["farmer_name"],
        "sub_queue_id": target_booking["sub_queue_id"],
        "center": matching_slot["center"] if matching_slot else None,
        "crop": matching_slot["crop"] if matching_slot else None,
        "time": matching_slot["time"] if matching_slot else None,
        "message": "Token valid. Farmer marked as ARRIVED.",
    }