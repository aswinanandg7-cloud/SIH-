"""
SIH PS 32 — Farmer-facing Telegram bot (demo version).

Flow: /start -> pick crop (Cereals/Pulses) -> type quantity (quintals)
-> tap "share location" -> bot says "Found your location!" and shows 3
centres for that crop with quantity remaining -> farmer picks a centre
-> backend books the quantity and auto-assigns one of the day's 4 time
slots based on how full that centre already is -> confirmation with
token, centre, assigned time, and quantity.

NOTE: for the demo, "Found your location!" is cosmetic — the location the
farmer shares isn't used to pick a centre yet (all matching centres for
the crop are shown, farmer picks by remaining quantity). Swap in real
distance-based sorting later if you want the location to actually drive
which centre appears first.

Talks to the backend in suggested_backend_main.py via:
  GET  /centers?crop=...
  POST /book
"""

import logging
import os

import httpx
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

# Conversation states
CHOOSING_CROP, TYPING_QUANTITY, WAITING_LOCATION, CHOOSING_CENTER = range(4)


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

    await query.edit_message_text(f"🌾 Crop: {crop}")
    await query.get_bot().send_message(
        chat_id=update.effective_chat.id,
        text="How many quintals are you bringing? (e.g. 5)",
    )
    return TYPING_QUANTITY


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

    location_button = KeyboardButton("📍 Share My Location", request_location=True)
    await update.message.reply_text(
        f"Got it — {quantity} quintals.\n\nTap below to share your location:",
        reply_markup=ReplyKeyboardMarkup([[location_button]], one_time_keyboard=True, resize_keyboard=True),
    )
    return WAITING_LOCATION


async def location_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop = context.user_data.get("crop")
    quantity = context.user_data.get("quantity")

    await update.message.reply_text("📍 Found your location!", reply_markup=ReplyKeyboardRemove())

    try:
        centers = await fetch_centers(crop)
    except httpx.HTTPError:
        await update.message.reply_text("⚠️ Couldn't reach the booking server. Send /start to retry.")
        return ConversationHandler.END

    # Only show centres that can actually take this quantity today
    open_centers = [c for c in centers if c["remaining_quintals"] >= quantity]

    if not open_centers:
        await update.message.reply_text(
            f"😕 No centre for {crop} has {quantity} quintals of space left today. Try a smaller "
            "quantity or check back tomorrow. (/start to retry)"
        )
        return ConversationHandler.END

    # Show up to 3 centres
    shown = open_centers[:3]
    keyboard = [
        [
            InlineKeyboardButton(
                f"{c['name']} — {c['remaining_quintals']:.0f}/{c['max_capacity_quintals']:.0f} qtl left",
                callback_data=f"center:{c['id']}",
            )
        ]
        for c in shown
    ]

    await update.message.reply_text(
        "Here are nearby centres with space:",
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
    quantity = context.user_data.get("quantity", 0)

    result, error = await book_center(farmer_name, farmer_id, center_id, quantity)

    if error:
        await query.edit_message_text(f"⚠️ Booking failed: {error}\n\nSend /start to try again.")
        return ConversationHandler.END

    await query.edit_message_text(
        "✅ Booking confirmed!\n\n"
        f"🎫 Token: {result['token']}\n"
        f"📍 Centre: {result['center']}\n"
        f"🕒 Assigned time slot: {result['time']}\n"
        f"⚖️ Quantity: {result['quantity_tons']} quintals\n\n"
        "Show this token at the centre gate on arrival. Keep it safe!"
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