# SIH Telegram Bot — Bilingual Quantity-Based Booking Flow

Farmer-facing Telegram bot for the AgroProcure slot-booking system. The
farmer picks a crop, picks a quantity (preset buttons or custom), shares
their GPS location, sees the centres with space, picks one, and gets a
confirmed booking — with a QR-code pass, an estimated MSP payout, and a
one-tap Google Maps link to the centre.

Fully bilingual: English and हिंदी.

> **This README is for teammates setting up/onboarding.** You need the
> Supabase project URL + an API key (Service Role recommended) to run the
> backend. If you have one of those from the project owner, follow the
> steps below.

## Repo placement

```
SIH-/
├── sih-backend/             FastAPI service (Supabase-backed) — run this first
├── sih-mobile-frontend/
└── sih-telegram-bot/        bot.py, this README
```

Architecture:

```
Telegram bot (sih-telegram-bot/bot.py)
        │  HTTP
        ▼
FastAPI backend (sih-backend/main.py)  ──  Supabase (Supabase Python SDK)
        │
        ▼
bookings / procurement_plans / slots tables
```

The bot does **not** talk to Supabase directly. It calls the backend's
HTTP API:
- `GET  /centers?crop=...`
- `POST /book`

The backend then reads/writes Supabase. The backend is already wired to
Supabase via the [supabase](https://pypi.org/project/supabase/) Python SDK
(`create_client` in `sih-backend/main.py`) — it only needs the credentials
in `sih-backend/.env` and the package installed.

## Flow in `bot.py` (`sih-telegram-bot/bot.py`)

| Step | Handler |
|---|---|
| `/start` → choose English / हिंदी | `start`, `language_chosen` |
| type full name | `name_received` |
| type Farmer ID / Aadhaar / Reg. number | `farmer_id_received` |
| pick crop (Cereals / Pulses) | `crop_chosen` |
| pick preset quantity or custom | `quantity_button_chosen`, `quantity_custom_received` |
| share GPS location | `ask_for_location`, `location_step` |
| pick a centre | `_show_centers` |
| confirmation + QR pass | `center_chosen` (`make_qr_image`, `haversine_km`) |

## 1. Get a bot token from BotFather

Telegram → **@BotFather** → `/newbot` → name it → copy the token.

## 2. Configure the bot

```bash
cd sih-telegram-bot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# paste your token into TELEGRAM_BOT_TOKEN — never paste it in chat/commits
# leave API_BASE_URL=http://127.0.0.1:8000 for local dev, or point it at a
# deployed backend URL for demo day
```

## 3. Run the backend (Supabase-backed)

The FastAPI backend lives in `sih-backend/`, **not** in this folder.

```bash
cd sih-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

You need the Supabase project **URL** and an **API key**. Find them in the
Supabase dashboard (owner: → **Project Settings → API** — copy the *Project
URL* and the **service_role** key, or the public *anon/publishable* key):

```bash
cp .env.example .env
# edit .env and set these two lines:
#   SUPABASE_URL="https://<project-ref>.supabase.co"
#   SUPABASE_SECRET_KEY="<your_service_role_or_publishable_key>"
```

Start the server:

```bash
uvicorn main:app --reload --port 8000
```

### Prerequisite check (runs at startup)

On boot the backend verifies the connection and that the required
tables/columns exist. Watch the logs:

- **`[STARTUP CHECK] Supabase config present.`** → good, `.env` is set.
- **`[STARTUP CHECK] Supabase schema verified OK.`** → tables/columns are
  there; you're ready to run the bot.
- A `[STARTUP CHECK] ...` **warning/error** → something is wrong; the server
  still boots, but `/centers` and `/book` will fail (and the bot will show
  its "couldn't reach the booking server" message). Fix `.env` or the
  schema before continuing.

The required Supabase tables and columns the backend reads/writes:

| Table | Required columns |
|---|---|
| `bookings` | `id`, `token`, `farmer_name`, `farmer_id`, `center_id`, `center_name`, `slot_id`, `crop`, `quantity_quintals`, `quantity_tons`, `time_slot`, `sub_queue_id`, `booking_date`, `status` |
| `procurement_plans` | `id`, `date`, `center_id`, `center_name`, `category`, `limit_tons` |
| `slots` | `id`, `center`, `crop`, `time`, `max_capacity` |

> 🔒 Keep `SUPABASE_SECRET_KEY` and `TELEGRAM_BOT_TOKEN` out of git — both
> `.env` files are gitignored. Only commit `.env.example` (blank values).

## 4. Run the bot

In a second terminal:

```bash
cd sih-telegram-bot
source venv/bin/activate
python bot.py
```

The bot logs `Bot starting, polling for updates against <API_BASE_URL> ...`.
Make sure the backend from step 3 is reachable at that URL.

## 5. Test it

1. `/start` → choose **English** or **हिंदी**.
2. Type your name, then your Farmer ID / Aadhaar / registration number.
3. Tap **Cereals** or **Pulses**.
4. Tap a preset quantity button (e.g. **20 Qtl**) — or **✏️ Custom Amount**
   and type a custom number to check that path too.
5. Tap **📍 Share GPS Location** (phone only — desktop Telegram often can't).
6. You should see up to 3 centres with space, sorted by remaining capacity,
   each showing `remaining/total qtl left`.
7. Tap one → you get a text confirmation (token, centre, assigned time
   slot, quantity, **MSP payout estimate**) followed by a **QR-code image**
   of the token.
8. `/cancel` at any step should reset cleanly.

## Notes & known issues

- **Quantity field naming:** the bot sends quantity under `quantity_tons`,
  but the value is actually in **quintals** (the backend stores it in
  `quantity_quintals` and derives real tons separately). This matches the
  backend, so booking math is correct — but the field name is misleading.
- **No distance sorting yet:** the backend's `/centers` response does not
  include latitude/longitude, so the bot currently sorts centres by
  *remaining capacity* rather than by distance. `haversine_km` is kept in
  `bot.py` ready for when the backend returns coordinates.
- **MSP rates are representative:** "Cereals" uses the wheat MSP and
  "Pulses" the gram (chana) MSP. MSP is announced fresh each marketing
  season — double-check at pib.gov.in / cacp.gov.in before your demo date.
- **No offline fallback:** the old fallback/offline mode was removed. If the
  backend is unreachable, the bot shows a "couldn't reach the booking
  server" message.
- **One booking per farmer isn't enforced** — decide if that's wanted.
- **Race condition:** the backend's capacity read + booking insert aren't in
  one transaction, so two farmers booking the last bit of capacity at the
  same instant could both succeed. Fine for a demo.
- **Preset quantities:** `QUANTITY_PRESETS` (default `[5, 10, 20, 50, 100]`)
  is defined at the top of `bot.py` if you want to change the buttons.
- **Bot token hygiene:** keep it out of commits/screenshots; `/revoke` +
  regenerate via BotFather if it ever leaks.
