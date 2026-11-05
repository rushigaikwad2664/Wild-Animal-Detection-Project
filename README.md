# Wild Animal Detection System

Real-time wild animal detection with YOLOv8 + YOLO-World, a Flask dashboard,
browser alarm and optional WhatsApp alerts (Twilio).

## Project structure
```
web_server.py      main app
chatbot.py         animal info replies
ai_advisor.py      safety tips
mobile_alert.py    WhatsApp alerts (Twilio)
detect.py          stand-alone webcam test
train.py, data.yaml  custom training (optional)
templates/         home, dashboard, alerts, analytics, contact .html  (your existing folder)
static/            alarm sound etc.                                    (your existing folder)
yolov8n.pt, yolov8s-world.pt   model files
```

## How to run
1. Install Python 3.10 - 3.12 (tick "Add Python to PATH") and a webcam.
2. Open a terminal in the project folder, then:
   ```
   python -m venv venv
   venv\Scripts\activate          (Windows)   |   source venv/bin/activate  (Mac/Linux)
   pip install -r requirements.txt
   ```
3. (Optional, for WhatsApp) `copy .env.example .env` and fill in your Twilio values.
4. Check the camera: `python test_camera.py`  (if your camera is not 0, set CAMERA_INDEX in .env)
5. Start: `python web_server.py`
6. Open http://127.0.0.1:5000/ and click once on the page so the browser allows the alarm sound.

## Notes
- YOLO-World needs the CLIP package. Ultralytics installs it on first run (needs `git` installed).
- If an animal such as tiger/lion never triggers, lower its value in `CLASS_CONFIDENCE`.
- Keep `.env` private. Do not upload it to GitHub.
