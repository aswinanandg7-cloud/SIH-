import random
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AgroProcure Unified API (SQLite Engine)")
# Enable CORS for Frontend & Bot Integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any frontend URL (React, Flutter, etc.)
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, OPTIONS, etc.
    allow_headers=["*"],  # Allows all headers
)

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

    # Create Procurement Plans Table for govt-agri-clerk daily planning
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS procurement_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            center_id INTEGER NOT NULL,
            center_name TEXT NOT NULL,
            category TEXT NOT NULL,
            limit_tons REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, center_id)
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


DEFAULT_PROCUREMENT_CENTERS = [
    {"center_id": 1, "center_name": "Center 1 - North Cereals Hub", "category": "Cereals", "limit_tons": 500.0},
    {"center_id": 2, "center_name": "Center 2 - Central Grain Silo", "category": "Cereals", "limit_tons": 450.0},
    {"center_id": 3, "center_name": "Center 3 - East Pulse Depot", "category": "Pulses", "limit_tons": 300.0},
    {"center_id": 4, "center_name": "Center 4 - South Legume Yard", "category": "Pulses", "limit_tons": 250.0},
    {"center_id": 5, "center_name": "Center 5 - West Gram Storage", "category": "Pulses", "limit_tons": 200.0},
]


class BookingRequest(BaseModel):
    farmer_name: str
    farmer_id: str
    slot_id: int


class CenterLimitItem(BaseModel):
    center_id: int
    center_name: str
    category: str
    limit_tons: float


class ProcurementPlanRequest(BaseModel):
    date: str
    plans: list[CenterLimitItem]



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


# 4. GET PROCUREMENT PLAN (For Clerk Daily Procurement Planning)
@app.get("/procurement-plan")
def get_procurement_plan(date: str = None):
    conn = get_db()
    cursor = conn.cursor()

    if date:
        # Check if plan exists for this exact date
        cursor.execute("SELECT * FROM procurement_plans WHERE date = ? ORDER BY center_id", (date,))
        rows = cursor.fetchall()
        if rows and len(rows) > 0:
            plans = [
                {
                    "center_id": r["center_id"],
                    "center_name": r["center_name"],
                    "category": r["category"],
                    "limit_tons": r["limit_tons"],
                }
                for r in rows
            ]
            conn.close()
            return {"date": date, "is_saved": True, "plans": plans}

    # If no plan for target date, fallback to the most recently saved plan across any date
    cursor.execute("SELECT DISTINCT date FROM procurement_plans ORDER BY id DESC LIMIT 1")
    last_date_row = cursor.fetchone()

    if last_date_row:
        last_date = last_date_row["date"]
        cursor.execute("SELECT * FROM procurement_plans WHERE date = ? ORDER BY center_id", (last_date,))
        rows = cursor.fetchall()
        plans = [
            {
                "center_id": r["center_id"],
                "center_name": r["center_name"],
                "category": r["category"],
                "limit_tons": r["limit_tons"],
            }
            for r in rows
        ]
        conn.close()
        return {"date": date, "is_saved": False, "copied_from_date": last_date, "plans": plans}

    # If no plan exists in database at all, return DEFAULT_PROCUREMENT_CENTERS
    conn.close()
    return {"date": date, "is_saved": False, "plans": DEFAULT_PROCUREMENT_CENTERS}


# 5. SAVE / SUBMIT PROCUREMENT PLAN
@app.post("/procurement-plan")
def save_procurement_plan(request: ProcurementPlanRequest):
    conn = get_db()
    cursor = conn.cursor()

    for item in request.plans:
        cursor.execute(
            """
            INSERT OR REPLACE INTO procurement_plans (date, center_id, center_name, category, limit_tons)
            VALUES (?, ?, ?, ?, ?)
            """,
            (request.date, item.center_id, item.center_name, item.category, item.limit_tons),
        )

    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Daily procurement plan for {request.date} submitted successfully!",
        "date": request.date,
        "saved_count": len(request.plans),
    }