# SIH Telegram Bot — Farmer Booking Flow

Farmer-facing Telegram bot for PS 32. Lets a farmer pick a crop, pick a slot,
and get back a 6-digit booking token — all via inline buttons, no typing.

Talks to the `sih-backend` FastAPI service (`GET /slots`, `POST /book`).

## Repo placement

Drop this folder in next to `sih-backend` and your frontend, e.g.:

```
your-repo/
├── sih-backend/        (main.py, requirements.txt, README.md)
├── sih-mobile-frontend/ (index.html, eslint.config.js, ...)
└── sih-telegram-bot/    (this folder)
```

## 1. Get a bot token from BotFather

1. Open Telegram, search for **@BotFather**, start a chat.
2. Send `/newbot`, give it a name and a username ending in `bot`.
3. BotFather replies with a token like `123456789:AAF...`. Copy it.

## 2. Install & configure

```bash
cd sih-telegram-bot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and paste your token into TELEGRAM_BOT_TOKEN
```

## 3. Run the backend first

The bot needs `sih-backend` running and reachable at `API_BASE_URL`
(defaults to `http://127.0.0.1:8000`):

```bash
cd ../sih-backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Leave that running in its own terminal.

## 4. Run the bot

In a second terminal:

```bash
cd sih-telegram-bot
source venv/bin/activate
python bot.py
```

You should see `Bot starting, polling for updates against http://127.0.0.1:8000 ...`

## 5. Test it

1. Open Telegram, find your bot by the username you gave BotFather, tap **Start** (or send `/start`).
2. Tap **Cereals** or **Pulses**.
3. Tap one of the time-slot buttons.
4. You should get back a confirmation with a 6-digit token, centre, and time.
5. Check it actually hit the backend: `curl http://127.0.0.1:8000/slots` — the
   `remaining` count for the slot you booked should have gone down by 1.
6. Try booking the same slot 10 times in a row (or drop `max_capacity` to 1 in
   `sih-backend/main.py`'s `initial_slots` for a quick test) to see the
   "that slot just filled up" message.

### Testing the bot without the backend running

If your teammates' server isn't up yet, you can point `API_BASE_URL` at a
throwaway mock. Quickest option — run this tiny FastAPI stub instead of the
real backend, then run the bot exactly as above:

```python
# mock_backend.py — not part of the real repo, just for standalone testing
from fastapi import FastAPI
app = FastAPI()

@app.get("/slots")
def slots():
    return {"slots": [
        {"id": 1, "center": "Center A", "crop": "Cereals", "time": "09:00 AM - 11:00 AM", "max_capacity": 10, "remaining": 3},
        {"id": 5, "center": "Center B", "crop": "Pulses", "time": "09:00 AM - 11:00 AM", "max_capacity": 10, "remaining": 3},
    ]}

@app.post("/book")
def book(body: dict):
    return {"status": "SUCCESS", "token": "111222", "sub_queue_id": "SLOT1-01",
            "center": "Center A", "time": "09:00 AM - 11:00 AM", "message": "Slot booked successfully!"}
```

Run with `uvicorn mock_backend:app --reload --port 8000`.

## Notes

- `farmer_name` and `farmer_id` are pulled automatically from the Telegram
  user (`full_name`, `id`) — the farmer never has to type anything.
- `sub_queue_id` from the `/book` response is intentionally never shown to
  the farmer; it's for gate staff only.
- If `/book` returns `400 Slot is full` (a race with another farmer), the
  bot shows a friendly message and tells them to `/start` again.
