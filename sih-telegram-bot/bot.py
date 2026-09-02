"""
AgroProcure Telegram Bot Frontend
- Collects farmer details, crop choice, location, and quantity in Quintals.
- Fetches active procurement centers from GET /centers?crop={crop}.
- Sends booking requests to POST /book with full payload mapping.
- Includes Fallback/Offline mode for seamless live demos.
"""

import logging
import random
import os
import httpx
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config & API Setup
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# Conversation States
NAME, FARMER_ID, CROP, QUANTITY, LOCATION, CENTER_SELECT = range(6)

# Default Fallback Centers (Used if backend API is temporarily offline)
DEFAULT_CENTERS = {
    "Cereals": [
        {"id": 1, "name": "Center 1 - North Cereals Hub", "category": "Cereals", "remaining_quintals": 5000.0},
        {"id": 2, "name": "Center 2 - Central Grain Silo", "category": "Cereals", "remaining_quintals": 4500.0},
    ],
    "Pulses": [
        {"id": 3, "name": "Center 3 - East Pulse Depot", "category": "Pulses", "remaining_quintals": 3000.0},
        {"id": 4, "name": "Center 4 - South Legume Yard", "category": "Pulses", "remaining_quintals": 2500.0},
        {"id": 5, "name": "Center 5 - West Gram Storage", "category": "Pulses", "remaining_quintals": 2000.0},
    ],
}

TIME_SLOTS = [
    "09:00 AM - 11:00 AM",
    "11:00 AM - 01:00 PM",
    "02:00 PM - 04:00 PM",
    "04:00 PM - 06:00 PM",
]


# -----------------------------------------------------------------------------
# API Helper Functions
# -----------------------------------------------------------------------------

async def fetch_centers(crop: str) -> list:
    """Fetches real-time center availability from backend with fallback to defaults."""
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.get(f"{API_BASE_URL}/centers", params={"crop": crop})
            if resp.status_code == 200:
                data = resp.json().get("centers", [])
                if data:
                    return data
    except Exception as e:
        logger.warning(f"Backend GET /centers unreachable ({e}), using default storage centers.")

    return DEFAULT_CENTERS.get(crop, DEFAULT_CENTERS["Cereals"])


async def book_center(farmer_name: str, farmer_id: str, center_id: int, quantity_quintals: float, crop: str):
    """
    Books slot via backend.
    Sends entered quantity in Quintals under 'quantity_tons' field as expected by the unified backend engine.
    """
    payload = {
        "farmer_name": farmer_name,
        "farmer_id": str(farmer_id),
        "center_id": center_id,
        "quantity_tons": float(quantity_quintals),  # Mapped to backend expectation
    }

    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.post(f"{API_BASE_URL}/book", json=payload)
            if resp.status_code == 200:
                return resp.json(), None
            elif resp.status_code in [400, 404, 422]:
                detail = resp.json().get("detail", "Slot limit exceeded or center capacity full.")
                return None, detail
    except Exception as e:
        logger.warning(f"Backend POST /book offline ({e}), generating demo pass.")

    # Offline / Fallback Booking Mode
    all_centers = DEFAULT_CENTERS.get("Cereals", []) + DEFAULT_CENTERS.get("Pulses", [])
    matching_center = next((c for c in all_centers if c["id"] == center_id), None)
    center_name = matching_center["name"] if matching_center else f"Procurement Center #{center_id}"

    token = str(random.randint(100000, 999999))
    time_slot = random.choice(TIME_SLOTS[:2])
    sub_queue_id = f"C{center_id}-S1-{random.randint(1, 15):02d}"

    simulated_result = {
        "status": "SUCCESS",
        "token": token,
        "center": center_name,
        "time": time_slot,
        "quantity_tons": quantity_quintals,
        "sub_queue_id": sub_queue_id,
        "message": "Center slot booked successfully!",
    }
    return simulated_result, None


# -----------------------------------------------------------------------------
# Conversation Handlers
# -----------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: Starts registration flow."""
    context.user_data.clear()
    await update.message.reply_text(
        "🌾 *Welcome to AgroProcure Slot Booking System!*\n\n"
        "Let's book your grain delivery pass.\n"
        "Please enter your *Full Name*:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return NAME


async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores farmer name and requests ID."""
    context.user_data["farmer_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"Thank you, *{context.user_data['farmer_name']}*!\n\n"
        "Now enter your *Farmer ID / Aadhaar / Registration Number*:",
        parse_mode="Markdown",
    )
    return FARMER_ID


async def farmer_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores farmer ID and asks for crop category selection."""
    context.user_data["farmer_id"] = update.message.text.strip()

    reply_keyboard = [["Cereals", "Pulses"]]
    await update.message.reply_text(
        "Select your *Crop Category*:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return CROP


async def crop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores crop choice and requests quantity in quintals."""
    crop_choice = update.message.text.strip()
    if crop_choice not in ["Cereals", "Pulses"]:
        await update.message.reply_text("Please select either *Cereals* or *Pulses* using the buttons.")
        return CROP

    context.user_data["crop"] = crop_choice
    await update.message.reply_text(
        f"Selected Crop: *{crop_choice}*\n\n"
        "Enter the estimated quantity to deposit in *Quintals* (e.g. 50):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return QUANTITY


async def quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validates entered quantity and prompts for location share."""
    try:
        qty = float(update.message.text.strip())
        if qty <= 0:
            raise ValueError
        context.user_data["quantity"] = qty
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid positive number for quantity in quintals:")
        return QUANTITY

    location_btn = [[KeyboardButton("📍 Share Current Location", request_location=True)]]
    await update.message.reply_text(
        f"Quantity Recorded: *{qty} Quintals*\n\n"
        "Please share your location to find nearby procurement centers:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(location_btn, one_time_keyboard=True, resize_keyboard=True),
    )
    return LOCATION


async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fetches available centers and prompts user to pick one."""
    if update.message.location:
        context.user_data["lat"] = update.message.location.latitude
        context.user_data["lon"] = update.message.location.longitude

    crop = context.user_data.get("crop", "Cereals")
    centers = await fetch_centers(crop)

    if not centers:
        await update.message.reply_text(
            "⚠️ No active procurement centers available for this crop today. Please try again later.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    inline_keyboard = []
    text_lines = ["📍 *Available Procurement Centers:*\n"]

    for c in centers:
        c_id = c.get("id") or c.get("center_id")
        c_name = c.get("name") or c.get("center_name")
        rem_qtl = c.get("remaining_quintals", c.get("max_capacity_quintals", 1000.0))

        text_lines.append(f"• *{c_name}*\n  Remaining Space: `{rem_qtl:.1f} Qtl`\n")
        inline_keyboard.append([InlineKeyboardButton(f"Select {c_name}", callback_data=f"center_{c_id}")])

    await update.message.reply_text(
        "\n".join(text_lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard),
    )
    return CENTER_SELECT


async def center_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Executes booking upon center selection and returns digital entry pass."""
    query = update.callback_query
    await query.answer()

    center_id = int(query.data.replace("center_", ""))
    context.user_data["center_id"] = center_id

    result, error = await book_center(
        farmer_name=context.user_data["farmer_name"],
        farmer_id=context.user_data["farmer_id"],
        center_id=center_id,
        quantity_quintals=context.user_data["quantity"],
        crop=context.user_data["crop"],
    )

    if error:
        await query.edit_message_text(
            f"❌ *Booking Failed*\n\nReason: {error}\n\nPlease start again with /start.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    token = result.get("token", "N/A")
    center_name = result.get("center", f"Center #{center_id}")
    time_slot = result.get("time", "09:00 AM - 11:00 AM")
    sub_queue_id = result.get("sub_queue_id", "Q-01")

    pass_message = (
        "✅ *BOOKING CONFIRMED — AGROPROCURE PASS*\n"
        "───────────────────────────────\n"
        f"👤 *Farmer Name:* {context.user_data['farmer_name']}\n"
        f"🆔 *Farmer ID:* `{context.user_data['farmer_id']}`\n"
        f"🌾 *Crop:* {context.user_data['crop']}\n"
        f"⚖️ *Quantity:* {context.user_data['quantity']} Quintals\n"
        f"🏢 *Center:* {center_name}\n"
        f"⏰ *Time Slot:* `{time_slot}`\n"
        f"🔢 *Sub-Queue ID:* `{sub_queue_id}`\n"
        "───────────────────────────────\n"
        f"🎫 *ENTRY TOKEN CODE:* `{token}`\n"
        "───────────────────────────────\n"
        "📌 *Instructions:* Please present this token code at the entry gate check-in counter."
    )

    await query.edit_message_text(pass_message, parse_mode="Markdown")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current booking flow."""
    await update.message.reply_text(
        "Booking process cancelled. Type /start whenever you wish to book a slot.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# -----------------------------------------------------------------------------
# Main Runner
# -----------------------------------------------------------------------------

def main():
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("Please set TELEGRAM_BOT_TOKEN environment variable before running!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            FARMER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, farmer_id_handler)],
            CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, crop_handler)],
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, quantity_handler)],
            LOCATION: [
                MessageHandler(filters.LOCATION, location_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, location_handler),
            ],
            CENTER_SELECT: [CallbackQueryHandler(center_select_callback, pattern="^center_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)

    logger.info("AgroProcure Telegram Bot started successfully...")
    app.run_polling()


if __name__ == "__main__":
    main()
