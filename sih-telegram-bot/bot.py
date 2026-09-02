"""
SIH PS 32 — Farmer-facing Telegram bot (demo version, with UX upgrades).

Flow: /start -> pick crop (Cereals/Pulses) -> pick a preset quantity or
type a custom one -> tap "share location" -> bot does real haversine
distance sorting against each centre's coordinates and shows the 3
nearest with quantity remaining -> farmer picks a centre -> backend books
the quantity and auto-assigns one of the day's 4 time slots -> bot sends
a text confirmation (with estimated MSP payout + Google Maps link) and a
QR code image of the token.

Talks to the backend in suggested_backend_main.py via:
  GET  /centers?crop=...
  POST /book

MSP RATES BELOW ARE REPRESENTATIVE, NOT LIVE: "Cereals" is priced at the
wheat MSP and "Pulses" at the gram (chana) MSP, since those are the two
broad categories the app uses. Government MSP rates change every
marketing season — confirm current figures at pib.gov.in / cacp.gov.in
before quoting them to judges or farmers.
"""

import logging
import math
import os
from io import BytesIO

import httpx
import qrcode
from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

CROPS = ["Cereals", "Pulses"]
QUANTITY_PRESETS = [5, 10, 20, 50, 100]

# Representative MSP rates (₹/quintal) — see disclaimer above. Update each
# marketing season.
MSP_PER_QUINTAL = {
    "Cereals": 2585,  # Wheat MSP, 2026-27 marketing year
    "Pulses": 5650,   # Gram (chana) MSP, 2025-26 Rabi marketing season
}

# Conversation states
CHOOSING_CROP, CHOOSING_QUANTITY, TYPING_QUANTITY, WAITING_LOCATION, CHOOSING_CENTER = range(5)


# --------------------------------------------------------------------------
# Backend API helpers
# --------------------------------------------------------------------------

async def fetch_centers(crop: str) -> list:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{API_BASE_URL}/centers", params={"crop": crop})
        resp.raise_for_status()
        return resp.json()["centers"]


async def book_center(farmer_name: str, farmer_id: str, center_id: int, quantity_tons: float):
    """Returns (result_dict, error_message). Exactly one will be None."""
    payload = {
        "farmer_name": farmer_name,
        "farmer_id": farmer_id,
        "center_id": center_id,
        "quantity_tons": quantity_tons,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{API_BASE_URL}/book", json=payload)

    if resp.status_code == 200:
        return resp.json(), None

    try:
        detail = resp.json().get("detail", "Something went wrong.")
    except Exception:
        detail = "Something went wrong."
    return None, detail


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def make_qr_image(token: str) -> BytesIO:
    qr = qrcode.make(f"AGROPROCURE:{token}")
    bio = BytesIO()
    bio.name = "token.png"
    qr.save(bio, "PNG")
    bio.seek(0)
    return bio


# --------------------------------------------------------------------------
# Conversation steps
# --------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    keyboard = [[InlineKeyboardButton(crop, callback_data=f"crop:{crop}")] for crop in CROPS]
    await update.message.reply_text(
        "👋 Welcome to AgroProcure!\n\nPlease choose your crop category:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_CROP


async def crop_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    crop = query.data.split(":", 1)[1]
    context.user_data["crop"] = crop

    keyboard = [
        [InlineKeyboardButton(f"{q} Qtl", callback_data=f"qty:{q}") for q in QUANTITY_PRESETS[:3]],
        [InlineKeyboardButton(f"{q} Qtl", callback_data=f"qty:{q}") for q in QUANTITY_PRESETS[3:]],
        [InlineKeyboardButton("✏️ Other Amount", callback_data="qty:other")],
    ]
    await query.edit_message_text(
        f"🌾 Crop: {crop}\n\nHow many quintals are you bringing?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_QUANTITY


async def quantity_button_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    if choice == "other":
        await query.edit_message_text("Please type the quantity in quintals (e.g. 7.5):")
        return TYPING_QUANTITY

    quantity = float(choice)
    context.user_data["quantity"] = quantity
    await query.edit_message_text(f"⚖️ Quantity: {quantity:g} quintals")
    return await ask_for_location(update, context)


async def quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        quantity = float(text)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a positive number, e.g. 5 or 2.5")
        return TYPING_QUANTITY

    context.user_data["quantity"] = quantity
    return await ask_for_location(update, context)


async def ask_for_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    quantity = context.user_data["quantity"]
    location_button = KeyboardButton("📍 Share My Location", request_location=True)
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Got it — {quantity:g} quintals.\n\nTap below to share your location:",
        reply_markup=ReplyKeyboardMarkup([[location_button]], one_time_keyboard=True, resize_keyboard=True),
    )
    return WAITING_LOCATION


async def location_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop = context.user_data.get("crop")
    quantity = context.user_data.get("quantity")
    loc = update.message.location

    await update.message.reply_text("📍 Found your location!", reply_markup=ReplyKeyboardRemove())

    try:
        centers = await fetch_centers(crop)
    except httpx.HTTPError:
        await update.message.reply_text("⚠️ Couldn't reach the booking server. Send /start to retry.")
        return ConversationHandler.END

    open_centers = [c for c in centers if c["remaining_quintals"] >= quantity]
    if not open_centers:
        await update.message.reply_text(
            f"😕 No centre for {crop} has {quantity:g} quintals of space left today. Try a smaller "
            "quantity or check back tomorrow. (/start to retry)"
        )
        return ConversationHandler.END

    for c in open_centers:
        c["distance_km"] = haversine_km(loc.latitude, loc.longitude, c["latitude"], c["longitude"])
    open_centers.sort(key=lambda c: c["distance_km"])

    shown = open_centers[:3]
    context.user_data["centers_by_id"] = {c["id"]: c for c in shown}

    keyboard = [
        [
            InlineKeyboardButton(
                f"{c['name']} — {c['distance_km']:.1f} km — {c['remaining_quintals']:.0f}/{c['max_capacity_quintals']:.0f} qtl left",
                callback_data=f"center:{c['id']}",
            )
        ]
        for c in shown
    ]

    await update.message.reply_text(
        "Nearest centres with space:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_CENTER


async def center_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    center_id = int(query.data.split(":", 1)[1])

    user = update.effective_user
    farmer_name = user.full_name or user.username or "Farmer"
    farmer_id = str(user.id)
    crop = context.user_data.get("crop")
    quantity = context.user_data.get("quantity", 0)

    result, error = await book_center(farmer_name, farmer_id, center_id, quantity)

    if error:
        await query.edit_message_text(f"⚠️ Booking failed: {error}\n\nSend /start to try again.")
        return ConversationHandler.END

    msp_rate = MSP_PER_QUINTAL.get(crop)
    payout_line = ""
    if msp_rate:
        payout = msp_rate * result["quantity_tons"]
        payout_line = (
            f"\n💰 MSP rate: ₹{msp_rate:,}/qtl\n"
            f"💳 Estimated payout: ₹{payout:,.0f} (indicative, on successful procurement)\n"
        )

    maps_line = ""
    lat, lon = result.get("latitude"), result.get("longitude")
    if lat is not None and lon is not None:
        maps_line = f"\n🗺️ Navigate: https://www.google.com/maps/dir/?api=1&destination={lat},{lon}\n"

    await query.edit_message_text(
        "✅ Booking confirmed!\n\n"
        f"🎫 Token: {result['token']}\n"
        f"📍 Centre: {result['center']}\n"
        f"🕒 Assigned time slot: {result['time']}\n"
        f"⚖️ Quantity: {result['quantity_tons']:g} quintals\n"
        f"{payout_line}"
        f"{maps_line}\n"
        "Show the QR code below at the centre gate on arrival."
    )

    qr_image = make_qr_image(result["token"])
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=qr_image,
        caption=f"🎫 Token {result['token']} — keep this safe!",
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled. Send /start to begin again.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and add your token."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_CROP: [CallbackQueryHandler(crop_chosen, pattern="^crop:")],
            CHOOSING_QUANTITY: [CallbackQueryHandler(quantity_button_chosen, pattern="^qty:")],
            TYPING_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, quantity_received)],
            WAITING_LOCATION: [MessageHandler(filters.LOCATION, location_received)],
            CHOOSING_CENTER: [CallbackQueryHandler(center_chosen, pattern="^center:")],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    app.add_handler(conv)

    logger.info("Bot starting, polling for updates against %s ...", API_BASE_URL)
    app.run_polling()


if __name__ == "__main__":
    main()