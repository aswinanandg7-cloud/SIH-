"""
AgroProcure Unified Backend API
- Integrates Frontend Clerk Daily Procurement Planner (sih-mobile-frontend)
- Integrates Farmer Quantity-based Booking & Slot Assignment (sih-telegram-bot)
- Provides Live Aggregated Reports & Gate Verification
"""

import datetime
import logging
import random
import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client, Client

logger = logging.getLogger("agroprocure")

load_dotenv()

app = FastAPI(
    title="AgroProcure Unified API (Supabase API Engine)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_PUBLISHABLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("SUPABASE_URL or SUPABASE_SECRET_KEY is missing. Add them to sih-backend/.env (see .env.example).")

def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase not configured in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# Required tables and, for each, the columns the backend actually reads/writes.
# Missing tables/columns are detected at startup so failures surface clearly
# instead of as cryptic errors on the first real request.
REQUIRED_SCHEMA = {
    "bookings": [
        "id", "token", "farmer_name", "farmer_id", "center_id", "center_name",
        "slot_id", "crop", "quantity_quintals", "quantity_tons",
        "time_slot", "sub_queue_id", "booking_date", "status",
    ],
    "procurement_plans": [
        "id", "date", "center_id", "center_name", "category", "limit_tons",
    ],
    "slots": [
        "id", "center", "crop", "time", "max_capacity",
    ],
}


def verify_supabase_config() -> list[str]:
    """Returns a list of human-readable configuration problems (empty if OK)."""
    problems = []
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_SECRET_KEY (or SUPABASE_PUBLISHABLE_KEY)")
    if missing:
        problems.append(
            "Supabase not configured: missing " + ", ".join(missing)
            + ". Add them to sih-backend/.env (see .env.example). "
            + "Until then every /centers and /book call will return HTTP 500."
        )
    return problems


def verify_supabase_schema(supabase: Client) -> list[str]:
    """Verifies the required tables/columns exist. Returns problems (empty if OK)."""
    problems = []
    for table, columns in REQUIRED_SCHEMA.items():
        try:
            # Fetching a single row proves the table exists; selecting a
            # required column proves that column exists (PostgREST errors on
            # unknown tables/columns).
            column = columns[0]
            supabase.table(table).select(column).limit(1).execute()
        except Exception as e:
            problems.append(f"Table '{table}' not usable: {e}")
            continue

        for col in columns[1:]:
            try:
                supabase.table(table).select(col).limit(1).execute()
            except Exception as e:
                problems.append(f"Table '{table}' is missing required column '{col}' ({e})")
    return problems


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Runs prerequisite checks on startup. Logs clear warnings (does not
    prevent the server from booting, but flags broken setup immediately)."""
    config_problems = verify_supabase_config()
    if config_problems:
        for p in config_problems:
            logger.warning("[STARTUP CHECK] %s", p)
    else:
        logger.info("[STARTUP CHECK] Supabase config present.")

        try:
            client = get_supabase()
            schema_problems = verify_supabase_schema(client)
            if schema_problems:
                for p in schema_problems:
                    logger.warning("[STARTUP CHECK] %s", p)
            else:
                logger.info("[STARTUP CHECK] Supabase schema verified OK.")
        except Exception as e:
            logger.error("[STARTUP CHECK] Could not reach Supabase to verify schema: %s", e)

    yield


app.router.lifespan_context = lifespan

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


class BookingRequest(BaseModel):
    farmer_name: str
    farmer_id: str
    center_id: Optional[int] = None
    quantity_tons: Optional[float] = None
    slot_id: Optional[int] = None
    date: Optional[str] = None


class CenterLimitItem(BaseModel):
    center_id: int
    center_name: str
    category: str
    limit_tons: float


class ProcurementPlanRequest(BaseModel):
    date: str
    plans: list[CenterLimitItem]


class StatusUpdateRequest(BaseModel):
    status: str


def generate_unique_token(supabase: Client) -> str:
    while True:
        token = str(random.randint(100000, 999999))
        res = supabase.table("bookings").select("token").eq("token", token).execute()
        if not res.data:
            return token


def get_active_plan_for_date(supabase: Client, target_date: str) -> list[dict]:
    res = supabase.table("procurement_plans").select("*").eq("date", target_date).order("center_id").execute()
    if res.data:
        return res.data

    res = supabase.table("procurement_plans").select("date").order("id", desc=True).limit(1).execute()
    if res.data:
        last_date = res.data[0]["date"]
        res_last = supabase.table("procurement_plans").select("*").eq("date", last_date).order("center_id").execute()
        if res_last.data:
            return res_last.data

    return DEFAULT_PROCUREMENT_CENTERS


@app.get("/centers")
def get_centers(crop: Optional[str] = Query(None), date: Optional[str] = Query(None)):
    today_str = date or datetime.date.today().isoformat()
    supabase = get_supabase()

    active_plans = get_active_plan_for_date(supabase, today_str)

    centers_result = []
    for center in active_plans:
        if crop and center["category"].strip().lower() != crop.strip().lower():
            continue

        center_id = center["center_id"]
        max_tons = center["limit_tons"]
        max_quintals = max_tons * 10.0

        res = supabase.table("bookings").select("quantity_quintals").eq("center_id", center_id).eq("booking_date", today_str).execute()
        filled_quintals = sum(float(b["quantity_quintals"]) for b in res.data) if res.data else 0.0
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

    return {"date": today_str, "centers": centers_result}


@app.post("/book")
def create_booking(request: BookingRequest):
    target_date = request.date or datetime.date.today().isoformat()
    supabase = get_supabase()

    if request.center_id is not None:
        active_plans = get_active_plan_for_date(supabase, target_date)
        target_center = next((c for c in active_plans if c["center_id"] == request.center_id), None)

        if not target_center:
            raise HTTPException(status_code=404, detail=f"Center #{request.center_id} not found")

        qty_quintals = float(request.quantity_tons or 0.0)
        if qty_quintals <= 0:
            raise HTTPException(status_code=400, detail="Booking quantity must be greater than zero")

        max_quintals = target_center["limit_tons"] * 10.0

        res = supabase.table("bookings").select("quantity_quintals").eq("center_id", request.center_id).eq("booking_date", target_date).execute()
        filled_so_far = sum(float(b["quantity_quintals"]) for b in res.data) if res.data else 0.0
        booking_count_today = len(res.data) if res.data else 0

        if filled_so_far + qty_quintals > max_quintals:
            raise HTTPException(
                status_code=400,
                detail=f"Center capacity exceeded! Remaining space: {max(0.0, max_quintals - filled_so_far):.1f} quintals",
            )

        quarter_size = max(1.0, max_quintals / 4.0)
        slot_index = min(3, int(filled_so_far // quarter_size))
        assigned_time = TIME_SLOTS[slot_index]

        token = generate_unique_token(supabase)
        sub_queue_id = f"C{target_center['center_id']}-S{slot_index + 1}-{booking_count_today + 1:02d}"

        new_booking = {
            "token": token,
            "farmer_name": request.farmer_name,
            "farmer_id": request.farmer_id,
            "center_id": target_center["center_id"],
            "center_name": target_center["center_name"],
            "crop": target_center["category"],
            "quantity_quintals": qty_quintals,
            "quantity_tons": qty_quintals / 10.0,
            "time_slot": assigned_time,
            "sub_queue_id": sub_queue_id,
            "booking_date": target_date,
            "status": "BOOKED"
        }
        
        supabase.table("bookings").insert(new_booking).execute()

        return {
            "status": "SUCCESS",
            "token": token,
            "center": target_center["center_name"],
            "time": assigned_time,
            "quantity_tons": qty_quintals,
            "sub_queue_id": sub_queue_id,
            "message": "Center slot booked successfully!",
        }

    elif request.slot_id is not None:
        res = supabase.table("slots").select("*").eq("id", request.slot_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Slot not found")
        target_slot = res.data[0]

        res_bookings = supabase.table("bookings").select("id", count="exact").eq("slot_id", request.slot_id).execute()
        booked_count = res_bookings.count if res_bookings.count else 0

        if booked_count >= target_slot["max_capacity"]:
            raise HTTPException(status_code=400, detail="Slot is full")

        sub_queue_id = f"SLOT{target_slot['id']}-{booked_count + 1:02d}"
        token = generate_unique_token(supabase)

        new_booking = {
            "token": token,
            "farmer_name": request.farmer_name,
            "farmer_id": request.farmer_id,
            "slot_id": target_slot["id"],
            "center_name": target_slot["center"],
            "crop": target_slot["crop"],
            "quantity_quintals": 10.0,
            "quantity_tons": 1.0,
            "time_slot": target_slot["time"],
            "sub_queue_id": sub_queue_id,
            "booking_date": target_date,
            "status": "BOOKED"
        }
        
        supabase.table("bookings").insert(new_booking).execute()

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
        raise HTTPException(status_code=400, detail="Must provide either center_id or slot_id")


@app.get("/slots")
def get_slots():
    supabase = get_supabase()
    res = supabase.table("slots").select("*").execute()
    slots = res.data if res.data else []

    slots_response = []
    for slot in slots:
        res_bookings = supabase.table("bookings").select("id", count="exact").eq("slot_id", slot["id"]).execute()
        booked_count = res_bookings.count if res_bookings.count else 0
        slots_response.append({
            "id": slot["id"],
            "center": slot["center"],
            "crop": slot["crop"],
            "time": slot["time"],
            "max_capacity": slot["max_capacity"],
            "remaining": max(0, slot["max_capacity"] - booked_count),
        })

    return {"slots": slots_response}


@app.post("/verify/{token}")
def verify_token(token: str):
    supabase = get_supabase()

    res = supabase.table("bookings").select("*").eq("token", token).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Invalid token code")

    booking = res.data[0]

    if booking["status"] == "ARRIVED":
        raise HTTPException(status_code=400, detail="This token has already been checked in")

    supabase.table("bookings").update({"status": "ARRIVED"}).eq("token", token).execute()

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
    return result


@app.get("/procurement-plan")
def get_procurement_plan(date: Optional[str] = None):
    supabase = get_supabase()

    if date:
        res = supabase.table("procurement_plans").select("*").eq("date", date).order("center_id").execute()
        if res.data:
            plans = [
                {
                    "center_id": r["center_id"],
                    "center_name": r["center_name"],
                    "category": r["category"],
                    "limit_tons": r["limit_tons"],
                }
                for r in res.data
            ]
            return {"date": date, "is_saved": True, "plans": plans}

    res = supabase.table("procurement_plans").select("date").order("id", desc=True).limit(1).execute()
    if res.data:
        last_date = res.data[0]["date"]
        res_last = supabase.table("procurement_plans").select("*").eq("date", last_date).order("center_id").execute()
        if res_last.data:
            plans = [
                {
                    "center_id": r["center_id"],
                    "center_name": r["center_name"],
                    "category": r["category"],
                    "limit_tons": r["limit_tons"],
                }
                for r in res_last.data
            ]
            return {"date": date, "is_saved": False, "copied_from_date": last_date, "plans": plans}

    return {"date": date, "is_saved": False, "plans": DEFAULT_PROCUREMENT_CENTERS}


@app.post("/procurement-plan")
def save_procurement_plan(request: ProcurementPlanRequest):
    supabase = get_supabase()

    for item in request.plans:
        supabase.table("procurement_plans").upsert({
            "date": request.date,
            "center_id": item.center_id,
            "center_name": item.center_name,
            "category": item.category,
            "limit_tons": item.limit_tons
        }, on_conflict="date, center_id").execute()

    return {
        "status": "SUCCESS",
        "message": f"Daily procurement plan for {request.date} submitted successfully!",
        "date": request.date,
        "saved_count": len(request.plans),
    }


@app.get("/booking/{token}")
def get_booking(token: str):
    supabase = get_supabase()
    res = supabase.table("bookings").select("*").eq("token", token).execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    return res.data[0]


@app.put("/booking/{token}/status")
def update_booking_status(token: str, request: StatusUpdateRequest):
    valid_statuses = ["BOOKED", "ARRIVED", "WEIGHED", "GRADED", "COLLECTED", "PAID"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    supabase = get_supabase()
    
    res = supabase.table("bookings").select("token").eq("token", token).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    supabase.table("bookings").update({"status": request.status}).eq("token", token).execute()
    
    return {"message": "Status updated successfully", "status": request.status}


@app.get("/live-report")
def get_live_report(date: Optional[str] = None):
    target_date = date or datetime.date.today().isoformat()
    supabase = get_supabase()

    active_plans = get_active_plan_for_date(supabase, target_date)

    total_tokens = 0
    total_procured_tons = 0.0
    total_capacity_tons = sum(p["limit_tons"] for p in active_plans)

    center_stats = []
    for center in active_plans:
        c_id = center["center_id"]
        c_limit_tons = center["limit_tons"]

        res = supabase.table("bookings").select("quantity_tons").eq("center_id", c_id).eq("booking_date", target_date).execute()
        
        c_tokens = len(res.data) if res.data else 0
        c_booked_tons = sum(float(b["quantity_tons"]) for b in res.data) if res.data else 0.0

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

    return {
        "date": target_date,
        "total_tokens_issued": total_tokens,
        "total_procured_tons": total_procured_tons,
        "total_capacity_tons": total_capacity_tons,
        "overall_capacity_utilization_pct": overall_utilization,
        "centers": center_stats,
    }
