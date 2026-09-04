with open("sih-telegram-bot/bot.py", "r") as f:
    content = f.read()

content = content.replace(
    '        except Exception:\n            detail = "Something went wrong."\n    except httpx.RequestError:\n\n\ndef haversine_km',
    '        except Exception:\n            detail = "Something went wrong."\n        return None, detail\n    except httpx.RequestError as e:\n        return None, f"Network error: {e}"\n\n\ndef haversine_km'
)

with open("sih-telegram-bot/bot.py", "w") as f:
    f.write(content)
