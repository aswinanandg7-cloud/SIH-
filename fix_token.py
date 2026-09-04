with open("sih-telegram-bot/bot.py", "r") as f:
    content = f.read()

bad_func = """def build_app() -> Application:


    app = Application.builder().token(BOT_TOKEN).build()"""

good_func = """def build_app():
    if not BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set.")
        return None
    app = Application.builder().token(BOT_TOKEN).build()"""

content = content.replace(bad_func, good_func)

with open("sih-telegram-bot/bot.py", "w") as f:
    f.write(content)
