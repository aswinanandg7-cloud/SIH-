with open("sih-backend/main.py", "r") as f:
    content = f.read()

# Replace the previous flawed webhook code
content = content.split("# Telegram Webhook Integration")[0]

webhook_code = """
# Telegram Webhook Integration
import sys
import os
import importlib

# Add telegram bot directory to path to allow importing despite hyphens
bot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sih-telegram-bot')
if bot_dir not in sys.path:
    sys.path.append(bot_dir)

try:
    bot_module = importlib.import_module("bot")
    bot_app = bot_module.build_app()
    from telegram import Update
except Exception as e:
    print(f"Failed to load bot module: {e}")
    bot_app = None

@app.post("/webhook")
async def telegram_webhook(request: Request):
    if not bot_app:
        raise HTTPException(status_code=500, detail="Telegram bot not configured")
    
    if not bot_app._initialized:
        await bot_app.initialize()
    
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    
    await bot_app.process_update(update)
    return {"ok": True}
"""
content = content + "\n" + webhook_code

with open("sih-backend/main.py", "w") as f:
    f.write(content)
