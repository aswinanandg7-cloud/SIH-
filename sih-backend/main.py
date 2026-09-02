import datetime
import random
import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AgroProcure Dynamic Engine (Unified)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "agroprocure.db"

TIME_SLOTS = [
    "09:00 AM - 11:00 AM",
    "11:00 AM - 01:00 PM",
    "02:00 PM - 04:00 PM",
    "04:00 PM - 06:00 PM",
]

DEFAULT_CENTERS = [
    {"center_id": 1, "center_name": "Center A", "category": "General", "limit_tons": 500.0},
    {"center_id": 2, "center_name": "Center B", "category": "General", "limit_tons": 500.0},
]


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Fixed Time Slots Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY,
            center TEXT NOT NULL,
            crop TEXT NOT NULL,
            time TEXT NOT NULL,
            slot_order INTEGER NOT NULL
        )
    """)

    # 2. Persistent Center Limits Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS center_limits (
            center_id INTEGER PRIMARY KEY,
            center_name TEXT NOT NULL,
            daily_limit_tons REAL NOT NULL
        )
    """)

    # 3. Enhanced Bookings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            token TEXT PRIMARY KEY,
            farmer_name TEXT NOT NULL,
            farmer_id TEXT NOT NULL,
            center_id INTEGER NOT NULL,
            center_name TEXT NOT NULL,
            slot_id INTEGER,
            crop TEXT NOT NULL,
            quantity_quintals REAL NOT NULL,
            quantity_tons REAL NOT NULL,
            sub_queue_id TEXT NOT NULL,
            status TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (slot_id) REFERENCES slots (id)
        )
    """)

    # Populate Initial Slots
    cursor.execute("SELECT COUNT(*) FROM slots")
    if cursor.fetchone()[0] == 0:
        initial_slots = [
            (1, "Center A", "General", "09:00 AM - 11:00 AM", 1),
            (2, "Center A", "General", "11:00 AM - 01:00 PM", 2),
            (3, "Center A", "General", "02:00 PM - 04:00 PM", 3),
            (4, "Center A", "General", "04:00 PM - 06:00 PM", 4),
            (5, "Center B", "General", "09:00 AM - 11:00 AM", 1),
            (6, "Center B", "General", "11:00 AM - 01:00 PM", 2),
            (7, "Center B", "General", "02:00 PM - 04:00 PM", 3),
            (8, "Center B", "General", "04:00 PM - 06:00 PM", 4),
        ]
        cursor.executemany(
            "INSERT INTO slots (id, center, crop, time, slot_order) VALUES (?, ?, ?, ?, ?)",
            initial_slots,
        )

    # Populate Default Center Limits
    cursor.execute("SELECT COUNT(*) FROM center_limits")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO center_limits (center_id, center_name, daily_limit_tons) VALUES (?, ?, ?)",
            [(1, "Center A", 500.0), (2, "Center B", 500.0)],
        )

    conn.commit()
    conn.close()


init_db()


# --- Pydantic Schemas ---

class BookingRequest(BaseModel):
    farmer_name: str
    farmer_id: str
    center_id: Optional[int] = 1
    center: Optional[str] = None
    crop: Optional[str] = "General"
    quantity_tons: Optional[float] = None
    quantity_quintals: Optional[float] = None
    booking_date: Optional[str] = None


class UpdateLimitRequest(BaseModel):
    center_id: int
    daily_limit_tons: float


def generate_unique_token(cursor) -> str:
    while True:
        token = str(random.randint(100000, 999999))
        cursor.execute("SELECT token FROM bookings WHERE token = ?", (token,))
        if not cursor.fetchone():
            return token


# --- Endpoints ---

# 1. GET CENTERS (For Telegram Bot Location / Selection)
@app.get("/centers")
def get_centers(crop: Optional[str] = Query(None), date_str: Optional[str] = Query(None)):
    target_date = date_str or str(datetime.date.today())
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM center_limits")
    centers = cursor.fetchall()

    result = []
    for c in centers:
        c_id = c["center_id"]
        c_name = c["center_name"]
        limit_tons = c["daily_limit_tons"]

        cursor.execute(
            "SELECT COALESCE(SUM(quantity_tons), 0.0) FROM bookings WHERE center_id = ? AND booking_date = ?",
            (c_id, target_date),
        )
        booked_tons = float(cursor.fetchone()[0])
        remaining_tons = max(0.0, limit_tons - booked_tons)

        result.append({
            "id": c_id,
            "name": c_name,
            "daily_limit_tons": limit_tons,
            "booked_tons": booked_tons,
            "remaining_tons": remaining_tons,
            "remaining_quintals": remaining_tons * 10.0,
        })

    conn.close()
    return {"date": target_date, "centers": result}


# 2. GET SLOTS & CENTER CAPACITY
@app.get("/slots")
def get_slots(center_id: int = 1):
    today_str = str(datetime.date.today())
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM center_limits WHERE center_id = ?", (center_id,))
    center_row = cursor.fetchone()
    daily_limit = center_row["daily_limit_tons"] if center_row else 500.0
    center_name = center_row["center_name"] if center_row else "Center A"

    cursor.execute(
        "SELECT COALESCE(SUM(quantity_tons), 0.0) FROM bookings WHERE center_id = ? AND booking_date = ?",
        (center_id, today_str),
    )
    total_booked = float(cursor.fetchone()[0])
    remaining_center_tons = max(0.0, daily_limit - total_booked)

    cursor.execute("SELECT * FROM slots WHERE center = ? ORDER BY slot_order", (center_name,))
    slots = cursor.fetchall()

    conn.close()
    return {
        "center_id": center_id,
        "center_name": center_name,
        "daily_limit_tons": daily_limit,
        "total_booked_tons": total_booked,
        "remaining_tons": remaining_center_tons,
        "slots": [dict(s) for s in slots],
    }


# 3. CREATE BOOKING (Dynamic 4-Slot Split + Edge Case Protection)
@app.post("/book")
def create_booking(request: BookingRequest):
    target_date = request.booking_date or str(datetime.date.today())
    conn = get_db()
    cursor = conn.cursor()

    # Calculate weight in tons
    if request.quantity_tons is not None:
        qty_tons = float(request.quantity_tons)
        qty_qtl = qty_tons * 10.0
    elif request.quantity_quintals is not None:
        qty_qtl = float(request.quantity_quintals)
        qty_tons = qty_qtl / 10.0
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Must provide quantity_tons or quantity_quintals")

    # Fetch center details
    cursor.execute("SELECT * FROM center_limits WHERE center_id = ?", (request.center_id,))
    center_row = cursor.fetchone()
    if not center_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Center #{request.center_id} not found")

    center_name = center_row["center_name"]
    daily_limit = float(center_row["daily_limit_tons"])

    # Calculate booked tons today
    cursor.execute(
        "SELECT COALESCE(SUM(quantity_tons), 0.0) FROM bookings WHERE center_id = ? AND booking_date = ?",
        (request.center_id, target_date),
    )
    total_booked = float(cursor.fetchone()[0])
    remaining_center_tons = daily_limit - total_booked

    if remaining_center_tons <= 0:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Daily limit for this procurement center has been completely filled. Please book for tomorrow.",
        )

    if qty_tons > remaining_center_tons:
        excess_tons = qty_tons - remaining_center_tons
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Requested quantity exceeds remaining daily limit by {excess_tons:.2f} tons. Max available today: {remaining_center_tons:.2f} tons. Please adjust or book for tomorrow.",
        )

    # Dynamic 4-slot determination
    slot_target = daily_limit / 4.0
    cursor.execute("SELECT * FROM slots WHERE center = ? ORDER BY slot_order", (center_name,))
    slots = cursor.fetchall()

    assigned_slot = slots[3] if slots else None
    assigned_time = TIME_SLOTS[3]
    slot_order = 4
    slot_id = None

    if slots:
        for s in slots:
            cursor.execute(
                "SELECT COALESCE(SUM(quantity_tons), 0.0) FROM bookings WHERE slot_id = ? AND booking_date = ?",
                (s["id"], target_date),
            )
            slot_booked = float(cursor.fetchone()[0])
            if slot_booked < slot_target:
                assigned_slot = s
                assigned_time = s["time"]
                slot_order = s["slot_order"]
                slot_id = s["id"]
                break

    cursor.execute(
        "SELECT COUNT(*) FROM bookings WHERE center_id = ? AND booking_date = ?",
        (request.center_id, target_date),
    )
    booking_count = cursor.fetchone()[0] + 1
    sub_queue_id = f"SLOT{slot_order}-{booking_count:02d}"

    token = generate_unique_token(cursor)

    cursor.execute(
        """
        INSERT INTO bookings (
            token, farmer_name, farmer_id, center_id, center_name, slot_id, crop,
            quantity_quintals, quantity_tons, sub_queue_id, status, booking_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token,
            request.farmer_name,
            request.farmer_id,
            request.center_id,
            center_name,
            slot_id,
            request.crop or "General",
            qty_qtl,
            qty_tons,
            sub_queue_id,
            "BOOKED",
            target_date,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "token": token,
        "center": center_name,
        "assigned_time": assigned_time,
        "sub_queue_id": sub_queue_id,
        "booked_tons": qty_tons,
        "remaining_center_tons": remaining_center_tons - qty_tons,
        "message": f"Successfully booked for {assigned_time}!",
    }


# 4. VERIFY TOKEN AT GATE
@app.post("/verify/{token}")
def verify_token(token: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bookings WHERE token = ?", (token,))
    target = cursor.fetchone()

    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="Invalid token code")

    if target["status"] == "ARRIVED":
        conn.close()
        raise HTTPException(status_code=400, detail="This token has already been used to check in")

    cursor.execute("UPDATE bookings SET status = 'ARRIVED' WHERE token = ?", (token,))
    conn.commit()

    conn.close()

    return {
        "status": "VERIFIED",
        "farmer_name": target["farmer_name"],
        "quantity_tons": target["quantity_tons"],
        "sub_queue_id": target["sub_queue_id"],
        "center": target["center_name"],
        "message": "Token valid. Farmer marked as ARRIVED.",
    }


# 5. ADMIN ENDPOINT TO UPDATE DAILY LIMIT
@app.post("/admin/set-limit")
def set_center_limit(request: UpdateLimitRequest):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO center_limits (center_id, center_name, daily_limit_tons)
        VALUES (?, ?, ?)
        ON CONFLICT(center_id) DO UPDATE SET daily_limit_tons = excluded.daily_limit_tons
        """,
        (request.center_id, f"Center {request.center_id}", request.daily_limit_tons),
    )

    conn.commit()
    conn.close()
    return {
        "status": "SUCCESS",
        "message": f"Daily limit for Center #{request.center_id} updated to {request.daily_limit_tons} tons.",
    }


# 6. GET LIVE REPORT (For Clerk Dashboard UI)
@app.get("/live-report")
def get_live_report(date_str: Optional[str] = None):
    target_date = date_str or str(datetime.date.today())
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM center_limits")
    centers = cursor.fetchall()

    total_tokens = 0
    total_booked_tons = 0.0
    total_capacity_tons = sum(c["daily_limit_tons"] for c in centers)

    center_stats = []
    for c in centers:
        c_id = c["center_id"]
        c_limit = c["daily_limit_tons"]

        cursor.execute(
            "SELECT COUNT(*), COALESCE(SUM(quantity_tons), 0.0) FROM bookings WHERE center_id = ? AND booking_date = ?",
            (c_id, target_date),
        )
        row = cursor.fetchone()
        c_tokens = int(row[0])
        c_tons = float(row[1])

        total_tokens += c_tokens
        total_booked_tons += c_tons

        center_stats.append({
            "center_id": c_id,
            "center_name": c["center_name"],
            "limit_tons": c_limit,
            "tokens_issued": c_tokens,
            "filled_tons": c_tons,
            "utilization_pct": round((c_tons / c_limit * 100.0), 1) if c_limit > 0 else 0.0,
        })

    conn.close()
    return {
        "date": target_date,
        "total_tokens_issued": total_tokens,
        "total_booked_tons": total_booked_tons,
        "total_capacity_tons": total_capacity_tons,
        "overall_utilization_pct": round((total_booked_tons / total_capacity_tons * 100.0), 1) if total_capacity_tons > 0 else 0.0,
        "centers": center_stats,
        }
    
