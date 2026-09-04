import os
import asyncio
from telegram import Update
from telegram.ext import Application
from .bot import conv, help_command, start

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Initialize the application without polling
app = None
if BOT_TOKEN:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(conv)
    app.add_handler(help_command) # wait, help_command is wrapped in CommandHandler
