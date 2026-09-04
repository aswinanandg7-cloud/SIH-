# -*- coding: utf-8 -*-
"""
SIH PS 32 — Farmer-facing Telegram bot (bilingual EN/HI version).
Connected to the Supabase-backed FastAPI backend (main__2_.py).

Flow:
  /start -> choose language (English / हिंदी)
         -> type full name
         -> type Farmer ID / Aadhaar / Registration Number
         -> pick crop (Cereals / Pulses)
         -> pick a preset quantity or type a custom one
         -> share GPS location OR view all centres directly (no location)
         -> pick a centre
         -> booking confirmed: text pass (MSP payout, queue position) + QR code image

Talks to the backend via:
  GET  /centers?crop=...
  POST /book   (center_id + quantity_tons, where quantity_tons is actually
                quintals — see note below)

FIELD NAMING NOTE: despite the name, "quantity_tons" carries a QUINTAL
value end-to-end in this system (the backend stores it as-is in
quantity_quintals and separately derives real tons as quantity_tons/10
for its own bookkeeping, but the value it *returns* to the bot under the
key "quantity_tons" is still quintals). The bot and MSP math below assume
quintals throughout, matching the backend, so calculations are correct —
but the field name itself is misleading and worth renaming if you touch
the backend again.

MSP RATES BELOW ARE REPRESENTATIVE, NOT LIVE: "Cereals" is priced at the
wheat MSP and "Pulses" at the gram (chana) MSP. Confirm current figures
at pib.gov.in / cacp.gov.in before quoting them to judges or farmers.

KNOWN LIMITATION: the backend's /centers and /book responses don't
include latitude/longitude, so "nearest centre" sorting never actually
activates — it silently falls back to sorting by remaining capacity
instead (see has_valid_coords below). Add lat/lon columns to the centers
data on the backend to turn real distance sorting back on.

PREREQUISITE: the backend requires SUPABASE_URL and
SUPABASE_SECRET_KEY/SUPABASE_PUBLISHABLE_KEY in its own .env. If those
aren't set, every /centers and /book call returns HTTP 500 and the bot
will show its generic "couldn't reach the booking server" message —
that's not a bot bug, it means the backend's Supabase config is missing.
"""

import logging
import math
import os
import re
import json
import asyncio
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
from telegram.constants import ParseMode
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

QUANTITY_PRESETS = [5, 10, 20, 50, 100]

MSP_PER_QUINTAL = {
    "Cereals": 2585,  # Wheat MSP, 2026-27 marketing year
    "Pulses": 5650,   # Gram (chana) MSP, 2025-26 Rabi marketing season
}

# Conversation states
LANGUAGE, NAME, FARMER_ID, CROP, QUANTITY_SELECT, QUANTITY_CUSTOM, LOCATION, CENTER_SELECT = range(8)


# --------------------------------------------------------------------------
# i18n
# --------------------------------------------------------------------------

TRANSLATIONS = {
    "en": {
        "choose_language": "🌐 Please choose your language:",
        "name_prompt": (
            "🌾 Welcome to MandiMitra Slot Booking System!\n\n"
            "Please enter your *Full Name*:"
        ),
        "name_invalid": "Please type a valid name (letters only, at least 2 characters).",
        "farmer_id_prompt": (
            "Thank you, *{name}*!\n\n"
            "Now enter your *Farmer ID / Aadhaar / Registration Number*:"
        ),
        "farmer_id_invalid": "Please enter a valid ID (at least 4 characters, letters/numbers only).",
        "crop_prompt": "🌾 Please choose your crop category:",
        "crop_cereals": "🌾 Cereals",
        "crop_pulses": "🫘 Pulses",
        "quantity_prompt": "Tap a preset quantity button or choose Custom:",
        "quantity_preset_btn": "{qty} Qtl",
        "quantity_custom_btn": "✏️ Custom Amount",
        "quantity_custom_prompt": "Please type the quantity in quintals (e.g. 7.5):",
        "quantity_invalid": "Please send a positive number, e.g. 5 or 2.5",
        "quantity_set": "⚖️ Quantity: {qty:g} quintals",
        "location_prompt": "Please share your location:",
        "share_location_btn": "📍 Share GPS Location",
        "found_location": "✅ Successfully found location!",
        "centers_heading_all": "🏢 Available centres:",
        "center_line": "{name} — {dist}{remaining:.0f}/{max:.0f} Qtl available",
        "no_centers": (
            "😕 No centre for {crop} has {qty:g} quintals of space left today. "
            "Try a smaller quantity or check back later. (/start to retry)"
        ),
        "server_error": "⚠️ Couldn't reach the booking server. Please try again in a moment. (/start to retry)",
        "booking_failed": "⚠️ Booking failed: {error}\n\nSend /start to try again.",
        "confirmation": (
            "✅ Booking confirmed!\n\n"
            "👤 Farmer Name: *{farmer_name}*\n"
            "🆔 Farmer ID: *{farmer_id}*\n"
            "🌾 Crop: *{crop}*\n"
            "⚖️ Quantity: *{quantity:g} quintals*\n"
            "🏢 Centre: *{center}*\n"
            "🕒 Time Slot: *{time}*\n"
            "🎫 Token Code: *{token}*\n"
            "{sub_queue_line}"
            "{payout_line}"
            "{maps_line}\n"
            "Show the QR code below at the centre gate on arrival."
        ),
        "sub_queue_line": "🔢 Queue Position: *{sub_queue_id}*\n",
        "payout_line": "💰 MSP Rate: ₹{rate:,}/Qtl\n💳 Estimated Payout: ₹{payout:,.0f} (indicative)\n",
        "maps_line": "🗺️ Navigate: {url}\n",
        "qr_caption": "🎫 Token {token} — show this QR code at gate check-in.",
        "help_text": (
            "/start — begin a new booking\n"
            "/status <token> — check booking status\n"
            "/cancel — cancel the current booking flow\n"
            "/help — show this message"
        ),
        "cancelled": "Cancelled. Send /start to begin again.",
        "status_missing_token": "Please provide your token number. For example: /status 123456",
        "status_not_found": "Booking not found for token: {token}",
        "status_display": "📌 *Booking Status*\n\n🎫 Token: *{token}*\n👤 Name: *{name}*\n🏢 Centre: *{center}*\n⚖️ Quantity: *{qty} quintals*\n📌 Status: *{status}*",
    },
    "hi": {
        "choose_language": "🌐 कृपया अपनी भाषा चुनें:",
        "name_prompt": (
            "🌾 मंडीमित्र स्लॉट बुकिंग प्रणाली में आपका स्वागत है!\n\n"
            "कृपया अपना *पूरा नाम* दर्ज करें:"
        ),
        "name_invalid": "कृपया एक मान्य नाम दर्ज करें (केवल अक्षर, कम से कम 2 अक्षर)।",
        "farmer_id_prompt": (
            "धन्यवाद, *{name}*!\n\n"
            "अब अपना *किसान आईडी / आधार / पंजीकरण संख्या* दर्ज करें:"
        ),
        "farmer_id_invalid": "कृपया एक मान्य आईडी दर्ज करें (कम से कम 4 अक्षर, केवल अक्षर/अंक)।",
        "crop_prompt": "🌾 कृपया अपनी फसल श्रेणी चुनें:",
        "crop_cereals": "🌾 अनाज / Cereals",
        "crop_pulses": "🫘 दालें / Pulses",
        "quantity_prompt": "निर्धारित मात्रा बटन चुनें या अन्य मात्रा दर्ज करें:",
        "quantity_preset_btn": "{qty} क्विंटल",
        "quantity_custom_btn": "✏️ अन्य मात्रा",
        "quantity_custom_prompt": "कृपया मात्रा क्विंटल में लिखें (उदाहरण: 7.5):",
        "quantity_invalid": "कृपया एक धनात्मक संख्या भेजें, जैसे 5 या 2.5",
        "quantity_set": "⚖️ मात्रा: {qty:g} क्विंटल",
        "location_prompt": "कृपया अपना स्थान साझा करें:",
        "share_location_btn": "📍 वर्तमान स्थान साझा करें",
        "found_location": "✅ स्थान सफलतापूर्वक मिल गया!",
        "centers_heading_all": "🏢 उपलब्ध केंद्र:",
        "center_line": "{name} — {dist}उपलब्ध क्षमता: {remaining:.0f}/{max:.0f} क्विंटल",
        "no_centers": (
            "😕 {crop} के लिए आज किसी भी केंद्र में {qty:g} क्विंटल जगह उपलब्ध नहीं है। "
            "कृपया कम मात्रा आज़माएँ या बाद में जांचें। (फिर से शुरू करने हेतु /start भेजें)"
        ),
        "server_error": "⚠️ बुकिंग सर्वर से संपर्क नहीं हो पाया। कृपया थोड़ी देर बाद पुनः प्रयास करें। (/start भेजें)",
        "booking_failed": "⚠️ बुकिंग विफल: {error}\n\nपुनः प्रयास हेतु /start भेजें।",
        "confirmation": (
            "✅ बुकिंग की पुष्टि हो गई है!\n\n"
            "👤 किसान का नाम: *{farmer_name}*\n"
            "🆔 किसान आईडी: *{farmer_id}*\n"
            "🌾 फसल: *{crop}*\n"
            "⚖️ मात्रा: *{quantity:g} क्विंटल*\n"
            "🏢 केंद्र: *{center}*\n"
            "🕒 समय स्लॉट: *{time}*\n"
            "🎫 टोकन कोड: *{token}*\n"
            "{sub_queue_line}"
            "{payout_line}"
            "{maps_line}\n"
            "कृपया केंद्र के गेट पर नीचे दिया गया क्यूआर कोड दिखाएं।"
        ),
        "sub_queue_line": "🔢 कतार स्थिति: *{sub_queue_id}*\n",
        "payout_line": "💰 एमएसपी दर: ₹{rate:,}/क्विंटल\n💳 अनुमानित भुगतान: ₹{payout:,.0f} (सांकेतिक)\n",
        "maps_line": "🗺️ रास्ता देखें: {url}\n",
        "qr_caption": "🎫 टोकन {token} — गेट चेक-इन पर यह क्यूआर कोड दिखाएं।",
        "help_text": (
            "/start — नई बुकिंग शुरू करें\n"
            "/status <token> — बुकिंग की स्थिति जांचें\n"
            "/cancel — वर्तमान बुकिंग रद्द करें\n"
            "/help — यह संदेश दिखाएं"
        ),
        "cancelled": "रद्द किया गया। फिर से शुरू करने के लिए /start भेजें।",
        "status_missing_token": "कृपया अपना टोकन नंबर प्रदान करें। उदाहरण के लिए: /status 123456",
        "status_not_found": "टोकन {token} के लिए बुकिंग नहीं मिली।",
        "status_display": "📌 *बुकिंग स्थिति*\n\n🎫 टोकन: *{token}*\n👤 नाम: *{name}*\n🏢 केंद्र: *{center}*\n⚖️ मात्रा: *{qty} क्विंटल*\n📌 स्थिति: *{status}*",
    },
}


def t(key: str, context: ContextTypes.DEFAULT_TYPE, **kwargs) -> str:
    lang = context.user_data.get("lang", "en")
    template = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key) or TRANSLATIONS["en"][key]
    return template.format(**kwargs) if kwargs else template


def escape_md(text: str) -> str:
    """Escape legacy Telegram Markdown special characters in user-supplied text."""
    return re.sub(r"([_*`\[\]])", r"\\\1", text)


# --------------------------------------------------------------------------
# Backend API helpers
# --------------------------------------------------------------------------

async def fetch_centers(crop: str) -> list:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{API_BASE_URL}/centers", params={"crop": crop})
        resp.raise_for_status()
        return resp.json()["centers"]


async def book_center(farmer_name: str, farmer_id: str, center_id: int, quantity_quintals: float):
    """Returns (result_dict, error_message). Exactly one will be None."""
    payload = {
        "farmer_name": farmer_name,
        "farmer_id": farmer_id,
        "center_id": center_id,
        "quantity_tons": quantity_quintals,  # backend field name is misleading; value is quintals
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{API_BASE_URL}/book", json=payload)

        if resp.status_code == 200:
            return resp.json(), None

        try:
            detail = resp.json().get("detail", "Something went wrong.")
        except Exception:
            detail = "Something went wrong."
        return None, detail
    except httpx.RequestError as e:
        return None, f"Network error: {e}"


async def fetch_booking(token: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{API_BASE_URL}/booking/{token}")
        if resp.status_code == 200:
            return resp.json(), None
        if resp.status_code == 404:
            return None, "Not Found"
        return None, "Error"
    except httpx.RequestError as e:
        return None, f"Network error: {e}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def make_qr_image(token: str) -> BytesIO:
    qr = qrcode.make(f"MANDIMITRA:{token}")
    bio = BytesIO()
    bio.name = "token.png"
    qr.save(bio, "PNG")
    bio.seek(0)
    return bio


# --------------------------------------------------------------------------
# Background Polling
# --------------------------------------------------------------------------

WATCH_FILE = "watches.json"

def load_watches():
    if os.path.exists(WATCH_FILE):
        with open(WATCH_FILE, "r") as f:
            return json.load(f)
    return {}

def save_watches(watches):
    with open(WATCH_FILE, "w") as f:
        json.dump(watches, f)

def add_watch(token, chat_id, status):
    watches = load_watches()
    watches[token] = {"chat_id": chat_id, "status": status}
    save_watches(watches)

async def background_polling(app: Application):
    while True:
        await asyncio.sleep(15)
        try:
            watches = load_watches()
            changed = False
            for token, data in list(watches.items()):
                result, error = await fetch_booking(token)
                if not error and result:
                    new_status = result.get("status")
                    if new_status and new_status != data["status"]:
                        chat_id = data["chat_id"]
                        msg = f"🔔 *Update!* Your booking ({token}) step has been processed.\n📌 New Status: *{new_status}*"
                        try:
                            await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)
                        except Exception as e:
                            logger.error(f"Failed to send update to %s: %s", chat_id, e)
                        
                        watches[token]["status"] = new_status
                        changed = True
                        if new_status in ["PAID", "COLLECTED"]:
                            del watches[token]
            if changed:
                save_watches(watches)
        except Exception as e:
            logger.error("Background polling error: %s", e)

async def post_init(app: Application):
    asyncio.create_task(background_polling(app))

# --------------------------------------------------------------------------
# Conversation steps
# --------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    keyboard = [
        [
            InlineKeyboardButton("🌾 English", callback_data="lang:en"),
            InlineKeyboardButton("🇮🇳 हिंदी", callback_data="lang:hi"),
        ]
    ]
    await update.message.reply_text(
        "🌐 Please choose your language / कृपया अपनी भाषा चुनें:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return LANGUAGE


async def language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":", 1)[1]
    context.user_data["lang"] = lang

    await query.edit_message_text(t("name_prompt", context), parse_mode=ParseMode.MARKDOWN)
    return NAME


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2 or not re.match(r"^[A-Za-z\u0900-\u097F .'-]+$", name):
        await update.message.reply_text(t("name_invalid", context))
        return NAME

    context.user_data["farmer_name"] = name
    await update.message.reply_text(
        t("farmer_id_prompt", context, name=escape_md(name)),
        parse_mode=ParseMode.MARKDOWN,
    )
    return FARMER_ID


async def farmer_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer_id = update.message.text.strip()
    if len(farmer_id) < 4 or not re.match(r"^[A-Za-z0-9]+$", farmer_id):
        await update.message.reply_text(t("farmer_id_invalid", context))
        return FARMER_ID

    context.user_data["farmer_id"] = farmer_id

    keyboard = [
        [InlineKeyboardButton(t("crop_cereals", context), callback_data="crop:Cereals")],
        [InlineKeyboardButton(t("crop_pulses", context), callback_data="crop:Pulses")],
    ]
    await update.message.reply_text(t("crop_prompt", context), reply_markup=InlineKeyboardMarkup(keyboard))
    return CROP


async def crop_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    crop = query.data.split(":", 1)[1]
    context.user_data["crop"] = crop

    row1 = [
        InlineKeyboardButton(t("quantity_preset_btn", context, qty=q), callback_data=f"qty:{q}")
        for q in QUANTITY_PRESETS[:3]
    ]
    row2 = [
        InlineKeyboardButton(t("quantity_preset_btn", context, qty=q), callback_data=f"qty:{q}")
        for q in QUANTITY_PRESETS[3:]
    ]
    row3 = [InlineKeyboardButton(t("quantity_custom_btn", context), callback_data="qty:other")]

    await query.edit_message_text(
        t("quantity_prompt", context),
        reply_markup=InlineKeyboardMarkup([row1, row2, row3]),
    )
    return QUANTITY_SELECT


async def quantity_button_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    if choice == "other":
        await query.edit_message_text(t("quantity_custom_prompt", context))
        return QUANTITY_CUSTOM

    quantity = float(choice)
    context.user_data["quantity"] = quantity
    await query.edit_message_text(t("quantity_set", context, qty=quantity))
    return await ask_for_location(update, context)


async def quantity_custom_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        quantity = float(text)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(t("quantity_invalid", context))
        return QUANTITY_CUSTOM

    context.user_data["quantity"] = quantity
    return await ask_for_location(update, context)


async def ask_for_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    # Plain text button (like the preset-quantity buttons), NOT the special
    # request-location "+" button. On Desktop/Web Telegram the request_location
    # button often sends its label as text with no location object, which made
    # the previous flow re-prompt forever. The backend doesn't actually use the
    # coordinates (centres are sorted by capacity), so a simple tap is enough.
    keyboard = [
        [KeyboardButton(t("share_location_btn", context))],
    ]
    await context.bot.send_message(
        chat_id=chat_id,
        text=t("location_prompt", context),
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return LOCATION


async def _show_centers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Demo MVP behaviour: always shows the same backend centre list for the
    chosen crop, regardless of the farmer's actual shared location. Real
    distance sorting can be reinstated later once the backend returns
    latitude/longitude (see haversine_km, kept below for that purpose)."""
    crop = context.user_data.get("crop")
    quantity = context.user_data.get("quantity")

    try:
        centers = await fetch_centers(crop)
    except Exception:
        await update.message.reply_text(t("server_error", context))
        return ConversationHandler.END

    open_centers = [c for c in centers if c["remaining_quintals"] >= quantity]
    if not open_centers:
        await update.message.reply_text(t("no_centers", context, crop=crop, qty=quantity))
        return ConversationHandler.END

    open_centers.sort(key=lambda c: c["remaining_quintals"], reverse=True)
    shown = open_centers[:3]
    context.user_data["centers_by_id"] = {c["id"]: c for c in shown}

    keyboard = []
    for c in shown:
        label = t(
            "center_line",
            context,
            name=c["name"],
            dist="",
            remaining=c["remaining_quintals"],
            max=c["max_capacity_quintals"],
        )
        keyboard.append([InlineKeyboardButton(label, callback_data=f"center:{c['id']}")])

    await update.message.reply_text(t("centers_heading_all", context), reply_markup=InlineKeyboardMarkup(keyboard))
    return CENTER_SELECT


async def location_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Accept any tap/message at this step (a real Location object, or the plain
    # text of the "Share GPS Location" button). The backend ignores coordinates,
    # so we don't gate on update.message.location — gating on it caused an
    # infinite re-prompt loop on Desktop/Web clients.
    logger.info("Location step received: type=%s", update.message.location or "text")
    await update.message.reply_text(t("found_location", context), reply_markup=ReplyKeyboardRemove())
    return await _show_centers(update, context)


async def center_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    center_id = int(query.data.split(":", 1)[1])

    farmer_name = context.user_data.get("farmer_name")
    farmer_id = context.user_data.get("farmer_id")
    crop = context.user_data.get("crop")
    quantity = context.user_data.get("quantity", 0)

    result, error = await book_center(farmer_name, farmer_id, center_id, quantity)

    if error:
        await query.edit_message_text(t("booking_failed", context, error=error))
        return ConversationHandler.END

    sub_queue_line = ""
    sub_queue_id = result.get("sub_queue_id")
    if sub_queue_id:
        sub_queue_line = t("sub_queue_line", context, sub_queue_id=sub_queue_id)

    payout_line = ""
    msp_rate = MSP_PER_QUINTAL.get(crop)
    if msp_rate:
        booked_qty = result.get("quantity_tons", quantity)  # actually quintals, see module docstring
        payout = msp_rate * booked_qty
        payout_line = t("payout_line", context, rate=msp_rate, payout=payout)

    maps_line = ""
    lat, lon = result.get("latitude"), result.get("longitude")
    if lat is not None and lon is not None:
        url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
        maps_line = t("maps_line", context, url=url)

    confirmation_text = t(
        "confirmation",
        context,
        farmer_name=escape_md(farmer_name),
        farmer_id=escape_md(farmer_id),
        crop=crop,
        quantity=result.get("quantity_tons", quantity),
        center=result.get("center", ""),
        time=result.get("time", ""),
        token=result.get("token", ""),
        sub_queue_line=sub_queue_line,
        payout_line=payout_line,
        maps_line=maps_line,
    )

    await query.edit_message_text(confirmation_text, parse_mode=ParseMode.MARKDOWN)

    qr_image = make_qr_image(result["token"])
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=qr_image,
        caption=t("qr_caption", context, token=result["token"]),
    )

    add_watch(result["token"], update.effective_chat.id, "BOOKED")

    context.user_data.clear()
    return ConversationHandler.END


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text(t("status_missing_token", context))
        return
    
    token = args[0]
    result, error = await fetch_booking(token)
    
    if error == "Not Found":
        await update.message.reply_text(t("status_not_found", context, token=escape_md(token)))
    elif error:
        await update.message.reply_text(t("server_error", context))
    else:
        status_text = t(
            "status_display",
            context,
            token=escape_md(result["token"]),
            name=escape_md(result["farmer_name"]),
            center=escape_md(result["center_name"]),
            qty=result["quantity_quintals"],
            status=escape_md(result["status"])
        )
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(t("help_text", context))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = t("cancelled", context)
    context.user_data.clear()
    await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------

def build_app():
    if not BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set.")
        return None
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [CallbackQueryHandler(language_chosen, pattern="^lang:")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)],
            FARMER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, farmer_id_received)],
            CROP: [CallbackQueryHandler(crop_chosen, pattern="^crop:")],
            QUANTITY_SELECT: [CallbackQueryHandler(quantity_button_chosen, pattern="^qty:")],
            QUANTITY_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, quantity_custom_received)],
            LOCATION: [MessageHandler((filters.LOCATION | filters.TEXT) & ~filters.COMMAND, location_step)],
            CENTER_SELECT: [CallbackQueryHandler(center_chosen, pattern="^center:")],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
        per_message=False,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("help", help_command))

    return app



def main() -> None:
    app = build_app()
    if app:
        logger.info("Bot starting, polling for updates against %s ...", API_BASE_URL)
        app.run_polling()

if __name__ == "__main__":
    main()