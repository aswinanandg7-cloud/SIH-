# SIH Telegram Bot — Quantity-Based Booking Flow (Demo)

Farmer picks a crop, types how much they're bringing, taps "share location"
(cosmetic for now), sees 3 centres with quantity left, picks one, and gets
a token with an **automatically assigned** time slot based on how full
that centre already is for the day.

## Does the code implement what we discussed? — status check

| Feature | Status |
|---|---|
| Centres have a daily max quantity capacity | ✅ in `suggested_backend_main.py` (`centers.max_capacity_quintals`) |
| Farmers book by quantity, not headcount | ✅ `/book` takes `quantity_tons` |
| 4 time slots per day, filled in quarters of centre capacity | ✅ `slot_index = filled_before // (max_capacity / 4)` |
| Bot shows "Found your location" + 3 centres with qty left | ✅ `location_received()` in `bot.py` |
| Location actually used to rank/filter centres | ❌ not yet — see note below |
| Old `/slots` + `slot_id` booking (previous version) | ❌ replaced — this is a breaking API change |

**What's still fake for the demo:** the "Found your location!" message
doesn't actually use GPS to sort centres — it shows whichever centres for
that crop have enough remaining quantity. That's fine for a demo ("here
are your options"), but if a judge asks "how did it pick these three,"
be ready to say it's currently by availability, with real distance-sorting
as a next step (bring back the haversine logic from before, applied to
these 3 centres, once real coordinates exist).

## ⚠️ This is a breaking backend change

`suggested_backend_main.py` replaces `/slots` + `slot_id`-based `/book`
with `/centers` + `center_id`-based `/book`. That affects:
- Your **frontend** (if it calls `/slots` or sends `slot_id`)
- Your **admin dashboard** (if it reads booking-by-slot data)

Talk to whoever owns those before swapping this in — don't just replace
`main.py` unannounced the night before demo.

## Repo placement

```
your-repo/
├── sih-backend/          (replace main.py with suggested_backend_main.py, after team sign-off)
├── sih-mobile-frontend/
└── sih-telegram-bot/      (bot.py, this folder)
```

## 1. Get a bot token from BotFather

1. Telegram → **@BotFather** → `/newbot` → name it, give it a `...bot` username.
2. Copy the token it gives you.

## 2. Install & configure

```bash
cd sih-telegram-bot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# paste your token into TELEGRAM_BOT_TOKEN in .env — never paste it in chat/commits
```

## 3. Run the backend

For this demo flow you need `suggested_backend_main.py` running (it has
the `/centers` endpoint the bot now calls — the old `main.py` doesn't).

```bash
cd sih-telegram-bot
cp suggested_backend_main.py /path/to/sih-backend/main.py   # after team agrees
cd /path/to/sih-backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Or just run it standalone for testing without touching the real repo:
```bash
cd sih-telegram-bot
pip install fastapi "uvicorn[standard]" pydantic
uvicorn suggested_backend_main:app --reload --port 8000
```

## 4. Run the bot

In a second terminal:
```bash
cd sih-telegram-bot
source venv/bin/activate
python bot.py
```

## 5. Test it

1. `/start` → tap **Cereals** or **Pulses**.
2. Type a quantity, e.g. `50`.
3. Tap **📍 Share My Location** (works on phone; desktop Telegram may not support it).
4. You'll see 3 centres with `remaining/total qtl left`.
5. Tap one → confirmation with token, centre, **assigned time slot**, quantity.
6. Verify the quarter-based assignment: `curl "http://127.0.0.1:8000/centers?crop=Cereals"`
   to see `filled_quintals` go up; book several times with quantities that
   cross a quarter boundary (e.g. centre cap 400 → quarter 100 → a booking
   that pushes filled past 100 should land in the 11 AM–1 PM slot, not 9–11).
7. Try a quantity bigger than any centre's remaining space — you should see
   "Centre is full for today" and no centres offered (or fewer than 3).
8. `/cancel` mid-flow should reset cleanly.

## Notes & known issues

- **Slot-boundary straddling**: a booking is assigned to the slot where its
  *starting* cumulative quantity falls. A booking that pushes past a
  quarter boundary is still counted entirely in the earlier slot. Fine for
  a demo; document it if asked.
- **No real distance ranking yet** — see status table above.
- **Race condition**: like before, `booked_today()` (read) and the booking
  `INSERT` (write) aren't wrapped in one transaction. Two farmers booking
  the last bit of capacity at the same instant could both succeed and
  overfill a centre. Wrap both in a single `BEGIN IMMEDIATE` transaction
  before demo day if you want this to be judge-proof.
- **Daily reset** relies on the server's local date (`date.today()`) — fine
  for a single-timezone demo, but note it if your team deploys across
  timezones later.
- **One booking per farmer isn't enforced** — same `farmer_id` can book
  multiple times today. Decide if that's wanted.
- **Bot token hygiene** — keep it out of commits/screenshots; `/revoke` +
  regenerate via BotFather if it ever leaks.