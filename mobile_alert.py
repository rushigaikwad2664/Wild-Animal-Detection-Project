"""WhatsApp + SMS alerts through Twilio.

Settings are read from the .env file (same folder as this file).
NEVER write your token directly in this code.
"""
import os

from twilio.rest import Client

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

_client = None


def _get_client():
    global _client
    if _client is None:
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        if not sid or not token or "PASTE_YOUR" in sid or "PASTE_YOUR" in token:
            raise RuntimeError("Put your real TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in the .env file")
        _client = Client(sid, token)
    return _client


def send_whatsapp_alert(animal, location="Pune"):
    from datetime import datetime
    import json

    from_whatsapp = os.getenv("TWILIO_FROM_WHATSAPP", "whatsapp:+14155238886")
    to_whatsapp = os.getenv("TWILIO_TO_WHATSAPP")
    content_sid = os.getenv("TWILIO_WHATSAPP_CONTENT_SID", "").strip()
    if not to_whatsapp:
        print("WhatsApp Error: TWILIO_TO_WHATSAPP is not set in .env")
        return False
    try:
        if content_sid:
            # Trial accounts must use a Twilio-provided template (ContentSid).
            # The template has two blanks: {{1}} and {{2}}.
            message = _get_client().messages.create(
                from_=from_whatsapp,
                to=to_whatsapp,
                content_sid=content_sid,
                content_variables=json.dumps({
                    "1": f"WILD ANIMAL ALERT: {animal.upper()} at {location}",
                    "2": datetime.now().strftime("%H:%M"),
                }),
            )
        else:
            # Normal custom message (works on paid accounts / inside 24h window)
            message = _get_client().messages.create(
                body=(f"\U0001F6A8 ALERT!\n\nWild Animal Detected: {animal.upper()}\n"
                      f"Location: {location}\nImmediate action required!"),
                from_=from_whatsapp,
                to=to_whatsapp,
            )
        print("\U0001F4F1 WhatsApp alert sent. SID:", message.sid)
        return True
    except Exception as e:
        print("WhatsApp Error:", e)
        return False


def send_sms_alert(animal, location="Pune"):
    from_sms = os.getenv("TWILIO_FROM_SMS")
    to_sms = os.getenv("TWILIO_TO_SMS")
    if not from_sms or not to_sms:
        return False   # SMS not set up, skip quietly
    try:
        message = _get_client().messages.create(
            body=f"ALERT! Wild animal detected: {animal.upper()} at {location}. Take action now!",
            from_=from_sms,
            to=to_sms,
        )
        print("📩 SMS sent. SID:", message.sid)
        return True
    except Exception as e:
        print("SMS Error:", e)
        return False


def send_telegram_alert(animal, location="Pune"):
    """Free alerts to your phone through a Telegram bot (any custom text)."""
    import json
    import urllib.request

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False   # Telegram not set up, skip quietly
    try:
        data = json.dumps({
            "chat_id": chat_id,
            "text": (f"\U0001F6A8 WILD ANIMAL ALERT!\n\nAnimal: {animal.upper()}\n"
                     f"Location: {location}\nImmediate action required!"),
        }).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = json.loads(resp.read().decode()).get("ok", False)
        print("\u2708\ufe0f Telegram alert sent" if ok else "Telegram Error: not ok")
        return ok
    except Exception as e:
        print("Telegram Error:", e)
        return False


def send_all_alerts(animal, location="Pune"):
    # Set USE_WHATSAPP=0 in .env to turn WhatsApp off (e.g. trial limits)
    if os.getenv("USE_WHATSAPP", "1") == "1":
        send_whatsapp_alert(animal, location)
    send_sms_alert(animal, location)
    send_telegram_alert(animal, location)
