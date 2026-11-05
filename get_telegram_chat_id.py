"""Prints your Telegram chat id. Send any message to your bot first, then run this."""
import json
import os
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not token:
    raise SystemExit("Put TELEGRAM_BOT_TOKEN in your .env file first.")

with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15) as r:
    data = json.loads(r.read().decode())

chats = {u["message"]["chat"]["id"] for u in data.get("result", []) if "message" in u}
if chats:
    for c in chats:
        print("Your chat id is:", c)
else:
    print("No messages found. Open your bot in Telegram, press Start, send 'hi', then run this again.")
