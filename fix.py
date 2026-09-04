with open('sih-telegram-bot/bot.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'logger.warning("TELEGRAM_BOT_TOKEN is not set.")' in line or 'return None' in line:
        continue
    new_lines.append(line)

with open('sih-telegram-bot/bot.py', 'w') as f:
    f.writelines(new_lines)

