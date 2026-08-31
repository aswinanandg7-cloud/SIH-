"""
SIH PS 32 — Farmer-facing Telegram bot.

Flow: /start -> pick crop (Cereals/Pulses) -> pick a time slot -> booking
confirmed with a 6-digit token. Farmer name/ID come straight from the
Telegram profile, so there is no typing anywhere in the flow.

Talks to the backend in sih-backend/main.py via:
  GET  /slots
  POST /book
"""

import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
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


# --------------------------------------------------------------------------
# Backend API helpers
# --------------------------------------------------------------------------

async def fetch_slots() -> list:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{API_BASE_URL}/slots")
        resp.raise_for_status()
        return resp.json()["slots"]


async def book_slot(farmer_name: str, farmer_id: str, slot_id: int):
    """Returns (result_dict, error_message). Exactly one will be None."""
    payload = {"farmer_name": farmer_name, "farmer_id": farmer_id, "slot_id": slot_id}
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
# Handlers
# --------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton(crop, callback_data=f"crop:{crop}")] for crop in CROPS]
    await update.message.reply_text(
        "👋 Welcome to AgroProcure!\n\nPlease choose your crop category:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_slots_for_crop(update: Update, crop: str) -> None:
    query = update.callback_query

    try:
        slots = await fetch_slots()
    except httpx.HTTPError:
        await query.edit_message_text(
            "⚠️ Couldn't reach the booking server. Please try again in a moment.\n"
            "(Send /start to retry.)"
        )
        return

    matching = [s for s in slots if s["crop"] == crop and s["remaining"] > 0]

    if not matching:
        await query.edit_message_text(
            f"😕 No open slots left for {crop} right now. Please check back later.\n"
            "(Send /start to try again.)"
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                f"{s['center']} — {s['time']} ({s['remaining']} left)",
                callback_data=f"slot:{s['id']}",
            )
        ]
        for s in matching
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back:crop")])

    await query.edit_message_text(
        f"🌾 {crop} — pick a time slot:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_booking(update: Update, slot_id: int) -> None:
    query = update.callback_query
    user = update.effective_user

    farmer_name = user.full_name or user.username or "Farmer"
    farmer_id = str(user.id)  # stable, typo-proof identifier

    result, error = await book_slot(farmer_name, farmer_id, slot_id)

    if error == "Slot is full":
        await query.edit_message_text(
            "⚠️ Sorry, that slot just filled up. Let's pick another one.\n\n"
            "Send /start to choose again."
        )
        return

    if error:
        await query.edit_message_text(f"⚠️ Booking failed: {error}\n\nSend /start to try again.")
        return

    await query.edit_message_text(
        "✅ Booking confirmed!\n\n"
        f"🎫 Token: {result['token']}\n"
        f"📍 Centre: {result['center']}\n"
        f"🕒 Time: {result['time']}\n\n"
        "Show this token at the centre gate on arrival. Keep it safe!"
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("crop:"):
        crop = data.split(":", 1)[1]
        await show_slots_for_crop(update, crop)

    elif data.startswith("slot:"):
        slot_id = int(data.split(":", 1)[1])
        await handle_booking(update, slot_id)

    elif data == "back:crop":
        keyboard = [[InlineKeyboardButton(crop, callback_data=f"crop:{crop}")] for crop in CROPS]
        await query.edit_message_text(
            "Please choose your crop category:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Send /start to book a slot.")


# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and add your token."
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot starting, polling for updates against %s ...", API_BASE_URL)
    app.run_polling()


if __name__ == "__main__":
    main()
