"""
AgroProcure — Farmer Telegram Bot (SIH Demo Version)

Flow:
1. /start -> Select Crop Category (Cereals / Pulses)
2. Quantity Selection -> Preset buttons (5, 10, 20, 50, 100 Qtl) or Custom amount
3. Location Step -> Tap "📍 Connect Location" -> Responds "Location connected successfully!"
4. Center Selection -> Shows storage centers for selected crop category
5. Confirmation -> Auto-assigned Time Slot, Token Code, MSP Payout & QR Code Pass
"""

import datetime
import logging
import os
import random
import warnings
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

# Suppress PTB callback warning
warnings.filterwarnings("ignore", message=".*per_message.*", category=Warning)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

CROPS = ["Cereals", "Pulses"]
QUANTITY_PRESETS = [5, 10, 20, 50, 100]

# Standard Govt MSP Rates (₹/quintal) for calculation
MSP_PER_QUINTAL = {
    "Cereals": 2585,  # Wheat MSP standard rate
    "Pulses": 5650,   # Gram / Chana MSP standard rate
}

# 4 Standard Daily Procurement Time Windows
TIME_SLOTS = [
    "09:00 AM - 11:00 AM",
    "11:00 AM - 01:00 PM",
    "02:00 PM - 04:00 PM",
    "04:00 PM - 06:00 PM",
]

# Fallback General Storage Centers (Matches Govt Procurement Centers)
DEFAULT_CENTERS = {
    "Cereals": [
        {
            "id": 1,
            "name": "Center 1 - North Cereals Hub",
            "category": "Cereals",
            "capacity_info": "480 / 500 MT available",
            "remaining_quintals": 4800,
            "distance_str": "3.5 km away",
        },
        {
            "id": 2,
            "name": "Center 2 - Central Grain Silo",
            "category": "Cereals",
            "capacity_info": "420 / 450 MT available",
            "remaining_quintals": 4200,
            "distance_str": "6.2 km away",
        },
    ],
    "Pulses": [
        {
            "id": 3,
            "name": "Center 3 - East Pulse Depot",
            "category": "Pulses",
            "capacity_info": "280 / 300 MT available",
            "remaining_quintals": 2800,
            "distance_str": "4.1 km away",
        },
        {
            "id": 4,
            "name": "Center 4 - South Legume Yard",
            "category": "Pulses",
            "capacity_info": "230 / 250 MT available",
            "remaining_quintals": 2300,
            "distance_str": "7.8 km away",
        },
        {
            "id": 5,
            "name": "Center 5 - West Gram Storage",
            "category": "Pulses",
            "capacity_info": "190 / 200 MT available",
            "remaining_quintals": 1900,
            "distance_str": "9.4 km away",
        },
    ],
}

# Conversation States
CHOOSING_CROP, CHOOSING_QUANTITY, TYPING_QUANTITY, WAITING_LOCATION, CHOOSING_CENTER = range(5)


# --------------------------------------------------------------------------
# Backend API Helpers (With Resilient Fallbacks for Demos)
# --------------------------------------------------------------------------

async def fetch_centers(crop: str) -> list:
    """Fetches real-time centers from backend, with graceful fallback to defaults."""
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.get(f"{API_BASE_URL}/centers", params={"crop": crop})
            if resp.status_code == 200:
                data = resp.json().get("centers", [])
                if data:
                    return data
    except Exception as e:
        logger.warning(f"Backend GET /centers unreachable ({e}), using default storage centers.")

    # Return built-in general centers for this crop category
    return DEFAULT_CENTERS.get(crop, DEFAULT_CENTERS["Cereals"])


async def book_center(farmer_name: str, farmer_id: str, center_id: int, quantity_quintals: float, crop: str):
    """Books via backend, or generates a clean simulated booking if offline."""
    payload = {
        "farmer_name": farmer_name,
        "farmer_id": str(farmer_id),
        "center_id": center_id,
        "quantity_tons": quantity_quintals,  # sends quantity value
    }

    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.post(f"{API_BASE_URL}/book", json=payload)
            if resp.status_code == 200:
                return resp.json(), None
            elif resp.status_code in [400, 404, 422]:
                detail = resp.json().get("detail", "Slot limit exceeded or unavailable.")
                return None, detail
    except Exception as e:
        logger.warning(f"Backend POST /book offline ({e}), generating demo pass.")

    # Fallback / Simulated Booking for Demo
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


def make_qr_image(token: str) -> BytesIO:
    """Generates a high-resolution QR code image for gate check-in."""
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=3,
    )
    qr.add_data(f"AGROPROCURE:TOKEN:{token}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    bio = BytesIO()
    bio.name = "token_qr.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio


# --------------------------------------------------------------------------
# Conversation Steps
# --------------------------------------------------------------------------

# Step 1: /start -> Choose Crop
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("🌾 Cereals (Wheat / Rice / Maize)", callback_data="crop:Cereals")],
        [InlineKeyboardButton("🫘 Pulses (Gram / Tur / Moong)", callback_data="crop:Pulses")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "👋 **Welcome to AgroProcure!** 🌾\n"
        "Government Agricultural Procurement & Token Management System\n\n"
        "Please select your **crop category** to begin:"
    )

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

    return CHOOSING_CROP


# Step 2: Crop Chosen -> Choose Quantity
async def crop_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    crop = query.data.split(":", 1)[1]
    context.user_data["crop"] = crop

    keyboard = [
        [
            InlineKeyboardButton(f"{q} Qtl", callback_data=f"qty:{q}")
            for q in QUANTITY_PRESETS[:3]
        ],
        [
            InlineKeyboardButton(f"{q} Qtl", callback_data=f"qty:{q}")
            for q in QUANTITY_PRESETS[3:]
        ],
        [InlineKeyboardButton("✏️ Custom / Other Amount", callback_data="qty:other")],
    ]

    await query.edit_message_text(
        f"🌾 **Crop Selected:** {crop}\n\n"
        "How many **quintals (Qtl)** are you bringing to the procurement center?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CHOOSING_QUANTITY


# Step 3A: Quantity Preset Button Clicked
async def quantity_button_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    choice = query.data.split(":", 1)[1]

    if choice == "other":
        await query.edit_message_text(
            "✏️ **Custom Quantity**\n\n"
            "Please type the quantity in quintals (e.g. `15` or `35.5`):",
            parse_mode="Markdown",
        )
        return TYPING_QUANTITY

    quantity = float(choice)
    context.user_data["quantity"] = quantity
    await query.edit_message_text(f"⚖️ **Quantity Confirmed:** {quantity:g} Quintals", parse_mode="Markdown")
    return await ask_for_location(update, context)


# Step 3B: Custom Quantity Typed by Farmer
async def quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        quantity = float(text)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Please enter a valid positive number for quintals (e.g. `25` or `12.5`):",
            parse_mode="Markdown",
        )
        return TYPING_QUANTITY

    context.user_data["quantity"] = quantity
    await update.message.reply_text(f"⚖️ **Quantity Confirmed:** {quantity:g} Quintals", parse_mode="Markdown")
    return await ask_for_location(update, context)


# Step 4: Ask for Location with 1-Tap Clickable Button
async def ask_for_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    quantity = context.user_data["quantity"]
    crop = context.user_data["crop"]

    keyboard = [
        [InlineKeyboardButton("📍 Connect Location / Find Nearby Centers", callback_data="loc:connect")]
    ]

    location_prompt = (
        f"🌾 **Crop:** {crop}\n"
        f"⚖️ **Quantity:** {quantity:g} Quintals\n\n"
        "📍 Tap the button below to connect your location and view available storage centers:"
    )

    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=location_prompt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return WAITING_LOCATION


# Step 5: Location Connected Successfully -> Show General Storage Centers
async def location_connected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Acknowledge callback query if triggered by button
    if update.callback_query:
        await update.callback_query.answer()
        chat_id = update.effective_chat.id
    else:
        chat_id = update.effective_chat.id

    crop = context.user_data.get("crop", "Cereals")
    quantity = context.user_data.get("quantity", 10.0)

    # Send Success message as requested
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ **Location connected successfully!** 📍\n\n"
             f"🔍 Showing active government procurement centers for **{crop}**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )

    # Fetch centers for this crop
    centers = await fetch_centers(crop)

    # Format center selection buttons
    keyboard = []
    for c in centers:
        c_id = c.get("id") or c.get("center_id")
        c_name = c.get("name") or c.get("center_name", f"Center #{c_id}")
        
        # Display remaining capacity
        rem_qtl = c.get("remaining_quintals")
        if rem_qtl is not None:
            cap_text = f"{rem_qtl:.0f} Qtl left"
        else:
            cap_text = c.get("capacity_info", "Space Available")

        dist_text = c.get("distance_str", "")
        button_label = f"🏢 {c_name} — {cap_text}"
        if dist_text:
            button_label = f"🏢 {c_name} ({dist_text}) — {cap_text}"

        keyboard.append([InlineKeyboardButton(button_label, callback_data=f"center:{c_id}")])

    keyboard.append([InlineKeyboardButton("⬅️ Back to Crop Selection", callback_data="nav:back_crop")])

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🏢 **Select your preferred procurement center ({crop}):**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CHOOSING_CENTER


# Step 6: Center Chosen -> Book & Send QR Code Token
async def center_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "nav:back_crop":
        return await start(update, context)

    center_id = int(data.split(":", 1)[1])

    user = update.effective_user
    farmer_name = user.full_name or user.username or "Farmer"
    farmer_id = str(user.id)
    crop = context.user_data.get("crop", "Cereals")
    quantity = context.user_data.get("quantity", 10.0)

    # Execute booking (API or demo fallback)
    result, error = await book_center(farmer_name, farmer_id, center_id, quantity, crop)

    if error:
        await query.edit_message_text(
            f"⚠️ **Booking Failed:** {error}\n\nPlease send /start to choose another center.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    # Calculate MSP Payout
    msp_rate = MSP_PER_QUINTAL.get(crop, 2585)
    payout = msp_rate * quantity

    token_code = result["token"]
    center_name = result["center"]
    time_slot = result["time"]
    sub_queue = result.get("sub_queue_id", f"C{center_id}-S1-01")

    confirmation_text = (
        "🎉 **BOOKING CONFIRMED!** ✅\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 **Token Number:** `{token_code}`\n"
        f"🏢 **Procurement Center:** {center_name}\n"
        f"🌾 **Commodity:** {crop}\n"
        f"⚖️ **Booked Quantity:** {quantity:g} Quintals\n"
        f"🕒 **Assigned Time Window:** {time_slot}\n"
        f"🔢 **Queue Pass ID:** `{sub_queue}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 **Govt MSP Rate:** ₹{msp_rate:,} / Quintal\n"
        f"💳 **Estimated DBT Payout:** ₹{payout:,.2f}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📲 **Arrival Instructions:**\n"
        "• Please reach the center during your designated time slot.\n"
        "• Show the **QR Code Pass** below at the entry gate for instant check-in."
    )

    await query.edit_message_text(confirmation_text, parse_mode="Markdown")

    # Send QR Code Image
    try:
        qr_image = make_qr_image(token_code)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=qr_image.getvalue(),
            filename=f"token_{token_code}.png",
            caption=(
                f"🎫 **Official Token Pass #{token_code}**\n"
                f"Farmer: {farmer_name} | Center: {center_name}\n"
                "Keep this QR code on your phone for gate verification."
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error sending QR code photo: {e}", exc_info=True)

    context.user_data.clear()
    return ConversationHandler.END


# Cancel Handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "🚫 Booking cancelled. Send /start anytime to begin a new slot booking.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# Help Command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ **AgroProcure Bot Guide:**\n\n"
        "• /start — Book a procurement token slot\n"
        "• /cancel — Cancel current booking session\n"
        "• /help — View this help guide\n\n"
        "Need assistance? Contact your district agricultural officer.",
        parse_mode="Markdown",
    )


# --------------------------------------------------------------------------
# Main Bot Entrypoint
# --------------------------------------------------------------------------

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Please set it in your .env file."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_CROP: [
                CallbackQueryHandler(crop_chosen, pattern="^crop:")
            ],
            CHOOSING_QUANTITY: [
                CallbackQueryHandler(quantity_button_chosen, pattern="^qty:")
            ],
            TYPING_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quantity_received)
            ],
            WAITING_LOCATION: [
                CallbackQueryHandler(location_connected, pattern="^loc:"),
                MessageHandler(filters.LOCATION, location_connected),
                MessageHandler(filters.TEXT & ~filters.COMMAND, location_connected),
            ],
            CHOOSING_CENTER: [
                CallbackQueryHandler(center_chosen, pattern="^center:"),
                CallbackQueryHandler(start, pattern="^nav:back_crop"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CommandHandler("help", help_command),
        ],
        per_message=False,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))

    logger.info("AgroProcure Telegram Bot started successfully! Polling against %s ...", API_BASE_URL)
    app.run_polling()


if __name__ == "__main__":
    main()
