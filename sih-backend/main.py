"""
AgroProcure Unified Backend API
- Integrates Frontend Clerk Daily Procurement Planner (sih-mobile-frontend)
- Integrates Farmer Quantity-based Booking & Slot Assignment (sih-telegram-bot)
- Provides Live Aggregated Reports & Gate Verification
"""

import datetime
import random
import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AgroProcure Unified API (SQLite Engine)", version="2.0.0")

# Enable CORS for Frontend & External Clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "agroprocure.db"

# 4 Standard Daily Time Slots
TIME_SLOTS = [
    "09:00 AM - 11:00 AM",
    "11:00 AM - 01:00 PM",
    "02:00 PM - 04:00 PM",
    "04:00 PM - 06:00 PM",
]

DEFAULT_PROCUREMENT_CENTERS = [
    {"center_id": 1, "center_name": "Center 1 - North Cereals Hub", "category": "Cereals", "limit_tons": 500.0},
    {"center_id": 2, "center_name": "Center 2 - Central Grain Silo", "category": "Cereals", "limit_tons": 450.0},
    {"center_id": 3, "center_name": "Center 3 - East Pulse Depot", "category": "Pulses", "limit_tons": 300.0},
    {"center_id": 4, "center_name": "Center 4 - South Legume Yard", "category": "Pulses", "limit_tons": 250.0},
    {"center_id": 5, "center_name": "Center 5 - West Gram Storage", "category": "Pulses", "limit_tons": 200.0},
]


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Slots table (legacy / fixed slots)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY,
            center TEXT NOT NULL,
            crop TEXT NOT NULL,
            time TEXT NOT NULL,
            max_capacity INTEGER NOT NULL
        )
    """)

    # 2. Procurement Plans table (stores daily limits set by Govt Agri Clerk)
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

    # 3. Enhanced Bookings table
    cursor.execute("""
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
        )
    """)

    # Populate Initial Static Slots if empty (for backward compatibility)
    cursor.execute("SELECT COUNT(*) FROM slots")
    if cursor.fetchone()[0] == 0:
        initial_slots = [
            (1, "Center 1 - North Cereals Hub", "Cereals", "09:00 AM - 11:00 AM", 50),
            (2, "Center 1 - North Cereals Hub", "Cereals", "11:00 AM - 01:00 PM", 50),
            (3, "Center 1 - North Cereals Hub", "Cereals", "02:00 PM - 04:00 PM", 50),
            (4, "Center 1 - North Cereals Hub", "Cereals", "04:00 PM - 06:00 PM", 50),
            (5, "Center 3 - East Pulse Depot", "Pulses", "09:00 AM - 11:00 AM", 50),
            (6, "Center 3 - East Pulse Depot", "Pulses", "11:00 AM - 01:00 PM", 50),
            (7, "Center 3 - East Pulse Depot", "Pulses", "02:00 PM - 04:00 PM", 50),
            (8, "Center 3 - East Pulse Depot", "Pulses", "04:00 PM - 06:00 PM", 50),
        ]
        cursor.executemany(
            "INSERT INTO slots (id, center, crop, time, max_capacity) VALUES (?, ?, ?, ?, ?)",
            initial_slots,
        )

    conn.commit()
    conn.close()


init_db()


# -----------------------------------------------------------------------------
# Pydantic Request Models
# -----------------------------------------------------------------------------

class BookingRequest(BaseModel):
    farmer_name: str
    farmer_id: str
    center_id: Optional[int] = None
    quantity_tons: Optional[float] = None  # quantity in quintals from bot
    slot_id: Optional[int] = None
    date: Optional[str] = None  # format: YYYY-MM-DD (defaults to today)


class CenterLimitItem(BaseModel):
    center_id: int
    center_name: str
    category: str
    limit_tons: float


class ProcurementPlanRequest(BaseModel):
    date: str
    plans: list[CenterLimitItem]


def generate_unique_token(cursor) -> str:
    while True:
        token = str(random.randint(100000, 999999))
        cursor.execute("SELECT token FROM bookings WHERE token = ?", (token,))
        if not cursor.fetchone():
            return token


def get_active_plan_for_date(cursor, target_date: str) -> list[dict]:
    """Helper to get center limits for a date, fallback to latest plan or defaults."""
    cursor.execute("SELECT * FROM procurement_plans WHERE date = ? ORDER BY center_id", (target_date,))
    rows = cursor.fetchall()
    if rows and len(rows) > 0:
        return [
            {
                "center_id": r["center_id"],
                "center_name": r["center_name"],
                "category": r["category"],
                "limit_tons": float(r["limit_tons"]),
            }
            for r in rows
        ]

    # Check most recent plan
    cursor.execute("SELECT DISTINCT date FROM procurement_plans ORDER BY id DESC LIMIT 1")
    last_date_row = cursor.fetchone()
    if last_date_row:
        cursor.execute("SELECT * FROM procurement_plans WHERE date = ? ORDER BY center_id", (last_date_row["date"],))
        rows = cursor.fetchall()
        return [
            {
                "center_id": r["center_id"],
                "center_name": r["center_name"],
                "category": r["category"],
                "limit_tons": float(r["limit_tons"]),
            }
            for r in rows
        ]

    return DEFAULT_PROCUREMENT_CENTERS


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

# 1. GET /centers (Called by Telegram Bot after Location Share)
@app.get("/centers")
def get_centers(crop: Optional[str] = Query(None), date: Optional[str] = Query(None)):
    today_str = date or datetime.date.today().isoformat()
    conn = get_db()
    cursor = conn.cursor()

    active_plans = get_active_plan_for_date(cursor, today_str)

    centers_result = []
    for center in active_plans:
        # Filter by crop if provided
        if crop and center["category"].strip().lower() != crop.strip().lower():
            continue

        center_id = center["center_id"]
        max_tons = center["limit_tons"]
        max_quintals = max_tons * 10.0

        # Calculate filled quintals booked for this center on target date
        cursor.execute(
            "SELECT COALESCE(SUM(quantity_quintals), 0.0) FROM bookings WHERE center_id = ? AND booking_date = ?",
            (center_id, today_str),
        )
        filled_quintals = float(cursor.fetchone()[0])
        remaining_quintals = max(0.0, max_quintals - filled_quintals)

        centers_result.append({
            "id": center_id,
            "name": center["center_name"],
            "category": center["category"],
            "max_capacity_tons": max_tons,
            "max_capacity_quintals": max_quintals,
            "filled_quintals": filled_quintals,
            "remaining_quintals": remaining_quintals,
            "remaining_tons": remaining_quintals / 10.0,
        })

    conn.close()
    return {"date": today_str, "centers": centers_result}


# 2. POST /book (Called by Telegram Bot OR Slot Frontend)
@app.post("/book")
def create_booking(request: BookingRequest):
    target_date = request.date or datetime.date.today().isoformat()
    conn = get_db()
    cursor = conn.cursor()

    # Branch A: Center & Quantity Based Booking (Telegram Bot flow)
    if request.center_id is not None:
        active_plans = get_active_plan_for_date(cursor, target_date)
        target_center = next((c for c in active_plans if c["center_id"] == request.center_id), None)

        if not target_center:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Center #{request.center_id} not found")

        qty_quintals = float(request.quantity_tons or 0.0)
        if qty_quintals <= 0:
            conn.close()
            raise HTTPException(status_code=400, detail="Booking quantity must be greater than zero")

        max_quintals = target_center["limit_tons"] * 10.0

        # Check existing bookings today
        cursor.execute(
            "SELECT COALESCE(SUM(quantity_quintals), 0.0), COUNT(*) FROM bookings WHERE center_id = ? AND booking_date = ?",
            (request.center_id, target_date),
        )
        row = cursor.fetchone()
        filled_so_far = float(row[0])
        booking_count_today = int(row[1])

        if filled_so_far + qty_quintals > max_quintals:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=f"Center capacity exceeded! Remaining space: {max(0.0, max_quintals - filled_so_far):.1f} quintals",
            )

        # Dynamic 4-quarter time slot assignment
        quarter_size = max(1.0, max_quintals / 4.0)
        slot_index = min(3, int(filled_so_far // quarter_size))
        assigned_time = TIME_SLOTS[slot_index]

        token = generate_unique_token(cursor)
        sub_queue_id = f"C{target_center['center_id']}-S{slot_index + 1}-{booking_count_today + 1:02d}"

        cursor.execute(
            """
            INSERT INTO bookings (
                token, farmer_name, farmer_id, center_id, center_name, slot_id, crop,
                quantity_quintals, quantity_tons, time_slot, sub_queue_id, booking_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                request.farmer_name,
                request.farmer_id,
                target_center["center_id"],
                target_center["center_name"],
                None,
                target_center["category"],
                qty_quintals,
                qty_quintals / 10.0,
                assigned_time,
                sub_queue_id,
                target_date,
                "BOOKED",
            ),
        )

        conn.commit()
        conn.close()

        return {
            "status": "SUCCESS",
            "token": token,
            "center": target_center["center_name"],
            "time": assigned_time,
            "quantity_tons": qty_quintals,
            "sub_queue_id": sub_queue_id,
            "message": "Center slot booked successfully!",
        }

    # Branch B: Legacy slot_id booking
    elif request.slot_id is not None:
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

        sub_queue_id = f"SLOT{target_slot['id']}-{booked_count + 1:02d}"
        token = generate_unique_token(cursor)

        cursor.execute(
            """
            INSERT INTO bookings (
                token, farmer_name, farmer_id, slot_id, center_name, crop,
                quantity_quintals, quantity_tons, time_slot, sub_queue_id, booking_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                request.farmer_name,
                request.farmer_id,
                target_slot["id"],
                target_slot["center"],
                target_slot["crop"],
                10.0,
                1.0,
                target_slot["time"],
                sub_queue_id,
                target_date,
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
            "quantity_tons": 10.0,
            "message": "Slot booked successfully!",
        }

    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Must provide either center_id or slot_id")


# 3. GET /slots (Legacy / Slot Visibility Component)
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
        slots_response.append({
            "id": slot["id"],
            "center": slot["center"],
            "crop": slot["crop"],
            "time": slot["time"],
            "max_capacity": slot["max_capacity"],
            "remaining": max(0, slot["max_capacity"] - booked_count),
        })

    conn.close()
    return {"slots": slots_response}


# 4. POST /verify/{token} (Gate Check-in Verification)
@app.post("/verify/{token}")
def verify_token(token: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bookings WHERE token = ?", (token,))
    booking = cursor.fetchone()

    if not booking:
        conn.close()
        raise HTTPException(status_code=404, detail="Invalid token code")

    if booking["status"] == "ARRIVED":
        conn.close()
        raise HTTPException(status_code=400, detail="This token has already been checked in")

    cursor.execute("UPDATE bookings SET status = 'ARRIVED' WHERE token = ?", (token,))
    conn.commit()

    result = {
        "status": "VERIFIED",
        "farmer_name": booking["farmer_name"],
        "sub_queue_id": booking["sub_queue_id"],
        "center": booking["center_name"],
        "crop": booking["crop"],
        "time": booking["time_slot"],
        "quantity_quintals": booking["quantity_quintals"],
        "quantity_tons": booking["quantity_tons"],
        "booking_date": booking["booking_date"],
        "message": "Token verified. Farmer marked as ARRIVED.",
    }
    conn.close()
    return result


# 5. GET /procurement-plan & POST /procurement-plan (Clerk Daily Planning)
@app.get("/procurement-plan")
def get_procurement_plan(date: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()

    if date:
        cursor.execute("SELECT * FROM procurement_plans WHERE date = ? ORDER BY center_id", (date,))
        rows = cursor.fetchall()
        if rows:
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

    conn.close()
    return {"date": date, "is_saved": False, "plans": DEFAULT_PROCUREMENT_CENTERS}


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


# 6. GET /live-report (Real-time Live Reporting for Frontend Clerk Tab 2)
@app.get("/live-report")
def get_live_report(date: Optional[str] = None):
    target_date = date or datetime.date.today().isoformat()
    conn = get_db()
    cursor = conn.cursor()

    active_plans = get_active_plan_for_date(cursor, target_date)

    total_tokens = 0
    total_procured_tons = 0.0
    total_capacity_tons = sum(p["limit_tons"] for p in active_plans)

    center_stats = []
    for center in active_plans:
        c_id = center["center_id"]
        c_limit_tons = center["limit_tons"]

        cursor.execute(
            "SELECT COUNT(*), COALESCE(SUM(quantity_tons), 0.0) FROM bookings WHERE center_id = ? AND booking_date = ?",
            (c_id, target_date),
        )
        c_tokens, c_booked_tons = cursor.fetchone()
        c_tokens = int(c_tokens)
        c_booked_tons = float(c_booked_tons)

        total_tokens += c_tokens
        total_procured_tons += c_booked_tons
        fill_pct = round((c_booked_tons / c_limit_tons * 100.0), 1) if c_limit_tons > 0 else 0.0

        center_stats.append({
            "center_id": c_id,
            "center_name": center["center_name"],
            "category": center["category"],
            "limit_tons": c_limit_tons,
            "tokens_distributed": c_tokens,
            "filled_tons": c_booked_tons,
            "fill_percentage": fill_pct,
        })

    overall_utilization = round((total_procured_tons / total_capacity_tons * 100.0), 1) if total_capacity_tons > 0 else 0.0

    conn.close()
    return {
        "date": target_date,
        "total_tokens_issued": total_tokens,
        "total_procured_tons": total_procured_tons,
        "total_capacity_tons": total_capacity_tons,
        "overall_capacity_utilization_pct": overall_utilization,
        "centers": center_stats,
    }
