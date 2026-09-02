# SIH Telegram Bot — Quantity-Based Booking Flow (Demo, with UX upgrades)

Farmer picks a crop, picks a quantity (preset buttons or custom), shares
location, sees the 3 **nearest** centres (real distance, not a guess) with
quantity left, picks one, and gets a token with an auto-assigned time
slot — plus a QR code pass, estimated MSP payout, and a one-tap Google
Maps link to the centre.

## What's new in this version

| Upgrade | Where |
|---|---|
| ⚡ Preset quantity buttons (5/10/20/50/100 Qtl + custom) | `bot.py` → `crop_chosen`, `quantity_button_chosen` |
| 📍 Real haversine distance sorting (no more placeholder coords) | `bot.py` → `haversine_km`, `location_received`; centre lat/lon now live in `suggested_backend_main.py` |
| 🗺️ One-tap Google Maps navigation link in confirmation | `bot.py` → `center_chosen` |
| 🎫 QR code digital pass (sent as an image, not just text) | `bot.py` → `make_qr_image`, sent via `send_photo` |
| 💰 Estimated MSP payout shown in confirmation | `bot.py` → `MSP_PER_QUINTAL` |

**Not implemented yet** (bigger effort, next in line): voice input,
multilingual support, `/status` + `/cancel_booking`, congestion balancer.

**On the MSP numbers:** "Cereals" is priced at the current wheat MSP
(₹2,585/qtl, 2026-27 marketing year) and "Pulses" at the current gram MSP
(₹5,650/qtl, 2025-26 Rabi season) — these are real government figures as
of this writing, but MSP is announced fresh each marketing season, so
double-check at pib.gov.in before your actual demo date in case it's
moved since.

## ⚠️ Still a breaking backend change

`suggested_backend_main.py` uses `/centers` + `center_id`-based `/book`,
not the original `/slots` + `slot_id`. If your frontend or admin
dashboard depend on the old shape, coordinate with your team before
swapping this in.

## Repo placement

```
your-repo/
├── sih-backend/          (replace main.py with suggested_backend_main.py, after team sign-off)
├── sih-mobile-frontend/
└── sih-telegram-bot/      (bot.py, this folder)
```

## 1. Get a bot token from BotFather

Telegram → **@BotFather** → `/newbot` → name it → copy the token.

## 2. Install & configure

```bash
cd sih-telegram-bot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# paste your token into TELEGRAM_BOT_TOKEN — never paste it in chat/commits
```

## 3. Run the backend

```bash
cd sih-telegram-bot
uvicorn suggested_backend_main:app --reload --port 8000
```

(Once your team signs off, this becomes the real `sih-backend/main.py`.)

## 4. Run the bot

In a second terminal:
```bash
cd sih-telegram-bot
source venv/bin/activate
python bot.py
```

## 5. Test it

1. `/start` → tap **Cereals** or **Pulses**.
2. Tap a preset quantity button, e.g. **20 Qtl** — or tap **✏️ Other Amount**
   and type a custom number to check that path too.
3. Tap **📍 Share My Location** (phone only — desktop Telegram often can't).
4. You should see 3 centres sorted nearest-first, each showing real km
   distance and `remaining/total qtl left`.
5. Tap one → you get a text confirmation (token, centre, assigned time
   slot, quantity, **MSP payout estimate**, **Google Maps link**) followed
   by a **QR code image** of the token.
6. Tap the Maps link — it should open directions to the centre's coordinates.
7. Scan the QR (any QR reader, e.g. your phone camera) — it should decode
   to `AGROPROCURE:<token>`.
8. Repeat with a location closer to a *different* demo centre (spoof via a
   Telegram location test, or just physically test with real GPS) to
   confirm the ordering actually changes — this is the easiest thing for a
   judge to poke at, so check it before demo day.
9. `/cancel` at any step should reset cleanly.

## Notes & known issues

- **Slot-boundary straddling**: a booking is assigned to the slot where its
  *starting* cumulative quantity falls; a booking that crosses a quarter
  boundary is still counted entirely in the earlier slot. Fine for a demo.
- **Race condition**: `booked_today()` (read) and the booking `INSERT`
  (write) aren't in one transaction — two farmers booking the last bit of
  capacity at the same instant could both succeed. Wrap in `BEGIN
  IMMEDIATE` before demo day if you want this judge-proof.
- **Daily reset** relies on server local date — fine for one timezone.
- **One booking per farmer isn't enforced** — decide if that's wanted.
- **Demo centre coordinates are placeholders** (spread around Delhi NCR).
  Swap in your real pitch-day centre locations in
  `suggested_backend_main.py`'s `initial_centers` before showing distance
  sorting live.
- **Bot token hygiene** — keep it out of commits/screenshots; `/revoke` +
  regenerate via BotFather if it ever leaks.