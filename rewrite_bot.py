import re

with open("sih-telegram-bot/bot.py", "r") as f:
    content = f.read()

# Replace main() with build_app()
content = content.replace("def main() -> None:", "def build_app() -> Application:\n    if not BOT_TOKEN:\n        logger.warning(\"TELEGRAM_BOT_TOKEN is not set.\")\n        return None\n")
content = content.replace("    app = Application.builder().token(BOT_TOKEN).build()", "    app = Application.builder().token(BOT_TOKEN).build()")

# Remove polling from build_app
content = content.replace("    logger.info(\"Bot starting, polling for updates against %s ...\", API_BASE_URL)\n    app.run_polling()", "    return app")

# Add a new main() for local testing
new_main = """
def main() -> None:
    app = build_app()
    if app:
        logger.info("Bot starting, polling for updates against %s ...", API_BASE_URL)
        app.run_polling()
"""
content = content.replace("if __name__ == \"__main__\":\n    main()", new_main + "\nif __name__ == \"__main__\":\n    main()")

with open("sih-telegram-bot/bot.py", "w") as f:
    f.write(content)
