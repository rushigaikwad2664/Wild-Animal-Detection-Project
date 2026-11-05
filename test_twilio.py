from mobile_alert import send_whatsapp_alert

print("sent" if send_whatsapp_alert("elephant", "Test location") else "FAILED - see error above")
