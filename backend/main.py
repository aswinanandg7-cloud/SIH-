import random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SIH Backend — Booking & Verification")

# --- Shared data (used by both /book and /verify) ---
db_slots = [
    # Center A — Cereals
    {"id": 1, "center": "Center A", "crop": "Cereals", "time": "09:00 AM - 11:00 AM", "max_capacity": 10},
    {"id": 2, "center": "Center A", "crop": "Cereals", "time": "11:00 AM - 01:00 PM", "max_capacity": 10},
    {"id": 3, "center": "Center A", "crop": "Cereals", "time": "02:00 PM - 04:00 PM", "max_capacity": 10},
    {"id": 4, "center": "Center A", "crop": "Cereals", "time": "04:00 PM - 06:00 PM", "max_capacity": 10},
    # Center B — Pulses
    {"id": 5, "center": "Center B", "crop": "Pulses", "time": "09:00 AM - 11:00 AM", "max_capacity": 10},
    {"id": 6, "center": "Center B", "crop": "Pulses", "time": "11:00 AM - 01:00 PM", "max_capacity": 10},
    {"id": 7, "center": "Center B", "crop": "Pulses", "time": "02:00 PM - 04:00 PM", "max_capacity": 10},
    {"id": 8, "center": "Center B", "crop": "Pulses", "time": "04:00 PM - 06:00 PM", "max_capacity": 10},
]

db_bookings = []


class BookingRequest(BaseModel):
    farmer_name: str
    farmer_id: str
    slot_id: int


def generate_unique_token():
    while True:
        token = str(random.randint(100000, 999999))
        if not any(b["token"] == token for b in db_bookings):
            return token


# --- GET /slots ---
@app.get("/slots")
def get_slots():
    slots_response = []
    for slot in db_slots:
        booked_count = len([b for b in db_bookings if b["slot_id"] == slot["id"]])
        slots_left = slot["max_capacity"] - booked_count
        slots_response.append({
            "id": slot["id"],
            "center": slot["center"],
            "crop": slot["crop"],
            "time": slot["time"],
            "max_capacity": slot["max_capacity"],
            "remaining": slots_left,
        })
    return {"slots": slots_response}


# --- POST /book ---
@app.post("/book")
def create_booking(request: BookingRequest):
    target_slot = next((s for s in db_slots if s["id"] == request.slot_id), None)
    if not target_slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    current_count = len([b for b in db_bookings if b["slot_id"] == request.slot_id])
    if current_count >= target_slot["max_capacity"]:
        raise HTTPException(status_code=400, detail="Slot is full")

    sub_slot_num = current_count + 1
    sub_queue_id = f"SLOT{target_slot['id']}-{sub_slot_num:02d}"
    token = generate_unique_token()

    booking_data = {
        "token": token,
        "farmer_name": request.farmer_name,
        "farmer_id": request.farmer_id,
        "slot_id": request.slot_id,
        "crop": target_slot["crop"],
        "sub_queue_id": sub_queue_id,
        "status": "BOOKED",
    }
    db_bookings.append(booking_data)

    return {
        "status": "SUCCESS",
        "token": token,
        "sub_queue_id": sub_queue_id,
        "center": target_slot["center"],
        "time": target_slot["time"],
        "message": "Slot booked successfully!",
    }


# --- POST /verify/{token} ---
@app.post("/verify/{token}")
def verify_token(token: str):
    target_booking = next((b for b in db_bookings if b["token"] == token), None)
    if not target_booking:
        raise HTTPException(status_code=404, detail="Invalid token code")

    if target_booking["status"] == "ARRIVED":
        raise HTTPException(status_code=400, detail="This token has already been used to check in")

    target_booking["status"] = "ARRIVED"
    matching_slot = next((s for s in db_slots if s["id"] == target_booking["slot_id"]), None)

    return {
        "status": "VERIFIED",
        "farmer_name": target_booking["farmer_name"],
        "sub_queue_id": target_booking["sub_queue_id"],
        "center": matching_slot["center"] if matching_slot else None,
        "crop": matching_slot["crop"] if matching_slot else None,
        "time": matching_slot["time"] if matching_slot else None,
        "message": "Token valid. Farmer marked as ARRIVED.",
    }