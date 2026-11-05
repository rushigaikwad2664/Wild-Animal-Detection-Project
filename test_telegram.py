from mobile_alert import send_telegram_alert

print("sent" if send_telegram_alert("elephant", "Test location") else "FAILED - check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
