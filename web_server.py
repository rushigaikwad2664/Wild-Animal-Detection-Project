"""Wild Animal Detection System - Flask web server.

Run:  python web_server.py   then open http://127.0.0.1:5000/
"""
import hashlib
import json
import os
import re
import secrets
import smtplib
import sqlite3
import sys
import threading
import time
from functools import wraps
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from email.message import EmailMessage

import cv2
from flask import (Flask, Response, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from ultralytics import YOLO

try:  # optional: reads settings from a .env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------- OPTIONAL MODULES ---------------- #
try:
    from chatbot import get_chat_response, FALLBACK_REPLY
except Exception as e:
    print("⚠️ Chatbot not available:", e)
    FALLBACK_REPLY = ""

    def get_chat_response(message):
        return "AI advisor is currently not available."

try:
    from ai_advisor import get_advice
except Exception as e:
    print("⚠️ AI advisor not available:", e)

    def get_advice(animal):
        return []

try:
    from mobile_alert import send_all_alerts
    MOBILE_ALERT = True
except Exception as e:
    print("⚠️ Mobile alert not available:", e)
    MOBILE_ALERT = False

# ---------------- CONFIG (override with .env) ---------------- #
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
LOCATION = os.getenv("ALERT_LOCATION", "Pune, Someshwarnagar")
HOST = os.getenv("HOST", "127.0.0.1")   # use 0.0.0.0 to open from phone on same Wi-Fi
PORT = int(os.getenv("PORT", "5000"))

ALERTS_FILE = os.path.join(BASE_DIR, "alerts_history.json")
MAX_HISTORY = 5000

ALARM_DURATION = 5
MOBILE_ALERT_COOLDOWN = 25
DETECTION_RESET_SECONDS = 3
SAME_ALERT_COOLDOWN = 10
MIN_BOX_AREA_RATIO = 0.03

REQUIRE_LOGIN = os.getenv("REQUIRE_LOGIN", "1") == "1"   # set 0 in .env to open all pages
DB_FILE = os.path.join(BASE_DIR, "users.db")

# Password-reset settings (put SMTP_* in .env to send real emails)
RESET_TOKEN_MINUTES = 30
APP_BASE_URL = os.getenv("APP_BASE_URL", f"http://127.0.0.1:{os.getenv('PORT', '5000')}").rstrip("/")


def load_secret_key():
    """Secret key signs login cookies. Kept in .secret_key so logins survive a restart."""
    key = os.getenv("SECRET_KEY")
    if key:
        return key
    path = os.path.join(BASE_DIR, ".secret_key")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    return key


app = Flask(__name__)
app.secret_key = load_secret_key()
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True


# ---------------- USER DATABASE (SQLite) ---------------- #
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            )""")
    print("✅ User database ready:", DB_FILE)


init_db()


def login_required(view):
    """Pages: send the visitor to the login page if not signed in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if REQUIRE_LOGIN and "user_id" not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def api_login_required(view):
    """JSON / video routes: answer 401 instead of redirecting."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if REQUIRE_LOGIN and "user_id" not in session:
            return jsonify({"error": "login required"}), 401
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    # makes {{ username }} available in every template (home.html uses it)
    return {"username": session.get("username")}


def safe_next(target):
    """Only allow redirects to pages on this site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("home")

# ---------------- MODELS ---------------- #
print("🔄 Loading YOLO models...")

try:
    coco_model = YOLO(os.path.join(BASE_DIR, "yolov8n.pt"))
    COCO_AVAILABLE = True
    print("✅ COCO YOLOv8 model loaded")
except Exception as e:
    print("❌ COCO model not loaded:", e)
    coco_model, COCO_AVAILABLE = None, False

try:
    world_model = YOLO(os.path.join(BASE_DIR, "yolov8s-world.pt"))
    YOLO_WORLD_AVAILABLE = True
    print("✅ YOLO-World model loaded")
except Exception as e:
    print("❌ YOLO-World model not loaded:", e)
    world_model, YOLO_WORLD_AVAILABLE = None, False

# COCO class IDs: elephant=20, bear=21, zebra=22, giraffe=23
COCO_ALLOWED_CLASS_IDS = [20, 21, 22, 23]
COCO_ANIMALS = ["elephant", "bear", "zebra", "giraffe"]
YOLO_WORLD_ANIMALS = ["leopard", "lion", "tiger", "deer", "monkey", "crocodile", "snake"]

# Minimum confidence per animal. If an animal (e.g. tiger) never triggers,
# lower its value (try 0.40-0.50). YOLO-World scores are usually lower than COCO.
CLASS_CONFIDENCE = {
    "elephant": 0.55, "bear": 0.60, "zebra": 0.60, "giraffe": 0.60,
    "leopard": 0.65, "lion": 0.65, "tiger": 0.65, "deer": 0.65,
    "monkey": 0.65, "crocodile": 0.68, "snake": 0.72,
}

if YOLO_WORLD_AVAILABLE:
    try:
        world_model.set_classes(YOLO_WORLD_ANIMALS)
        print("✅ YOLO-World classes:", YOLO_WORLD_ANIMALS)
    except Exception as e:
        print("❌ YOLO-World class setting error:", e)
        YOLO_WORLD_AVAILABLE = False

# ---------------- CAMERA ---------------- #
def open_camera():
    if sys.platform.startswith("win"):
        return cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    return cv2.VideoCapture(CAMERA_INDEX)


cap = open_camera()
print("✅ Camera started" if cap.isOpened() else "❌ Camera NOT working (check CAMERA_INDEX)")

# ---------------- SHARED STATE ---------------- #
animal_detected = False
current_active_labels = []
total_detections = 0
last_detection_time = 0.0
last_alert_time = 0.0
event_active = False
last_event_signature = ""
alarm_until = 0.0
alarm_event_id = 0
last_alert_signature_time = {}

latest_jpeg = None
frame_lock = threading.Lock()
alerts_lock = threading.Lock()

alerts_history = []
if os.path.exists(ALERTS_FILE):
    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            alerts_history = json.load(f)
    except Exception:
        alerts_history = []


# ---------------- HELPERS ---------------- #
def valid_confidence(label, conf):
    return conf >= CLASS_CONFIDENCE.get(label, 0.70)


def valid_box_area(frame, x1, y1, x2, y2):
    h, w = frame.shape[:2]
    if h * w <= 0:
        return False
    return (max(0, x2 - x1) * max(0, y2 - y1)) / (h * w) >= MIN_BOX_AREA_RATIO


def save_alerts():
    """Atomic write so the JSON file is never left half-written."""
    try:
        tmp = ALERTS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(alerts_history, f, indent=4)
        os.replace(tmp, ALERTS_FILE)
    except Exception as e:
        print("❌ Alert save error:", e)


def run_model(model, frame, source, allowed, color, **kwargs):
    """Run one model, return list of labels that passed all filters."""
    found = []
    for r in model(frame, verbose=False, **kwargs):
        for box in r.boxes:
            label = model.names[int(box.cls[0])].lower().strip()
            conf = float(box.conf[0])
            if label not in allowed or not valid_confidence(label, conf):
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            if not valid_box_area(frame, x1, y1, x2, y2):
                continue
            found.append(label)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            cv2.putText(frame, f"{source}: {label} {conf:.2f}",
                        (x1, max(y1 - 10, 25)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return found


def detect_frame_both_models(frame):
    labels = []
    if COCO_AVAILABLE:
        try:
            labels += run_model(coco_model, frame, "COCO", COCO_ANIMALS, (0, 0, 255),
                                conf=0.55, iou=0.55, classes=COCO_ALLOWED_CLASS_IDS)
        except Exception as e:
            print("❌ COCO detection error:", e)
    if YOLO_WORLD_AVAILABLE:
        try:
            labels += run_model(world_model, frame, "WORLD", YOLO_WORLD_ANIMALS, (0, 255, 255),
                                conf=0.65, iou=0.55)
        except Exception as e:
            print("❌ YOLO-World detection error:", e)
    labels = list(dict.fromkeys(labels))
    return frame, bool(labels), labels


def _send_mobile(label):
    try:
        send_all_alerts(label, LOCATION)
    except Exception as e:
        print("❌ Mobile alert error:", e)


def update_state(detected, labels, now):
    """Alert / cooldown logic (same behaviour as before)."""
    global animal_detected, current_active_labels, total_detections
    global last_detection_time, last_alert_time, event_active
    global last_event_signature, alarm_until, alarm_event_id

    if detected and labels:
        animal_detected = True
        current_active_labels = labels
        last_detection_time = now
        signature = ",".join(sorted(labels))

        is_new = (not event_active) or (signature != last_event_signature)
        if now - last_alert_signature_time.get(signature, 0) < SAME_ALERT_COOLDOWN:
            is_new = False

        if is_new:
            event_active = True
            last_event_signature = signature
            last_alert_signature_time[signature] = now
            total_detections += len(labels)
            alarm_until = now + ALARM_DURATION
            alarm_event_id += 1

            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with alerts_lock:
                for label in labels:
                    alerts_history.insert(0, {
                        "animal": label.capitalize(),
                        "location": LOCATION,
                        "timestamp": time_str,
                        "status": "Active",
                    })
                del alerts_history[MAX_HISTORY:]
                save_alerts()
            print("🚨 Animal alert:", labels)

            if MOBILE_ALERT and now - last_alert_time > MOBILE_ALERT_COOLDOWN:
                last_alert_time = now
                # separate thread so the video doesn't freeze while Twilio responds
                threading.Thread(target=_send_mobile, args=(labels[0],), daemon=True).start()
    elif now - last_detection_time > DETECTION_RESET_SECONDS:
        animal_detected = False
        current_active_labels = []
        event_active = False
        last_event_signature = ""


def draw_status(frame):
    if animal_detected and current_active_labels:
        cv2.putText(frame, "DANGER: Wild Animal Detected", (25, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
        cv2.putText(frame, "Detected: " + ", ".join(current_active_labels).title(), (25, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    else:
        cv2.putText(frame, "SAFE: No Wild Animal", (25, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)


# ---------------- BACKGROUND CAMERA THREAD ---------------- #
# One thread reads the camera and runs YOLO. Browser tabs only receive the
# latest JPEG, so several open pages no longer fight over the same camera.
def camera_loop():
    global latest_jpeg
    if not cap.isOpened():
        print("❌ Camera loop not started: camera is not available")
        return
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue
        try:
            frame, detected, labels = detect_frame_both_models(frame)
        except Exception as e:
            print("❌ Detection error:", e)
            detected, labels = False, []

        update_state(detected, labels, time.time())
        draw_status(frame)

        ok, buf = cv2.imencode(".jpg", frame)
        if ok:
            with frame_lock:
                latest_jpeg = buf.tobytes()


def generate_frames():
    while True:
        with frame_lock:
            jpg = latest_jpeg
        if jpg is None:
            time.sleep(0.1)
            continue
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
        time.sleep(0.03)


# ---------------- ROUTES ---------------- #
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/alerts")
@login_required
def alerts():
    with alerts_lock:
        history = list(alerts_history)
    return render_template(
        "alerts.html",
        alerts=history,
        active_count=len(current_active_labels),
        handled_count=sum(1 for a in history if a.get("status") == "Handled"),
        total_detections=total_detections,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/analytics")
@login_required
def analytics():
    with alerts_lock:
        history = list(alerts_history)

    animal_counter = Counter()
    date_counter = defaultdict(int)
    for a in history:
        animal_counter[a.get("animal", "Unknown")] += 1
        ts = a.get("timestamp", "")
        if ts:
            date_counter[ts.split(" ")[0]] += 1

    return render_template(
        "analytics.html",
        total_records=len(history),
        active_count=sum(1 for a in history if a.get("status") == "Active"),
        handled_count=sum(1 for a in history if a.get("status") == "Handled"),
        animal_labels=list(animal_counter.keys()),
        animal_values=list(animal_counter.values()),
        time_labels=list(date_counter.keys()),
        time_values=list(date_counter.values()),
    )


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    fullname = request.form.get("fullname", "").strip()
    email = request.form.get("email", "").strip().lower()
    uname = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")

    error = None
    if not (fullname and email and uname and password):
        error = "Please fill in all fields."
    elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        error = "Please enter a valid email address."
    elif not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", uname):
        error = "Username must be 3-30 characters: letters, numbers, _ . - only."
    elif len(password) < 6:
        error = "Password must be at least 6 characters."
    elif password != confirm:
        error = "Passwords do not match."

    if error:
        flash(error, "danger")
        return render_template("register.html"), 400

    try:
        with db() as conn:
            conn.execute(
                "INSERT INTO users (fullname, email, username, password_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (fullname, email, uname, generate_password_hash(password),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
    except sqlite3.IntegrityError:
        flash("That username or email is already registered.", "danger")
        return render_template("register.html"), 409

    flash("Account created! Please log in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    ident = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    with db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE lower(username) = lower(?) OR email = lower(?)",
            (ident, ident),
        ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Wrong username or password.", "danger")
        return render_template("login.html"), 401

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return redirect(safe_next(request.args.get("next")))


def send_reset_email(to_email, link):
    """Sends the reset link by email. Without SMTP settings the link is printed in the terminal."""
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    pwd = os.getenv("SMTP_PASSWORD", "").strip()
    if not (host and user and pwd):
        print("\n🔑 PASSWORD RESET LINK (email not configured, development mode):\n   ", link, "\n")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = "Reset your Wild AI Detection password"
        msg["From"] = os.getenv("SMTP_FROM", user)
        msg["To"] = to_email
        msg.set_content(
            "Hello,\n\nWe received a request to reset your password.\n"
            f"Open this link within {RESET_TOKEN_MINUTES} minutes:\n\n{link}\n\n"
            "If you did not ask for this, you can ignore this email.\n"
        )
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as smtp:
            smtp.starttls()
            smtp.login(user, pwd)
            smtp.send_message(msg)
        print("📧 Password reset email sent")
        return True
    except Exception as e:
        print("❌ Reset email error:", e)
        print("🔑 Reset link (use this instead):", link)
        return False


def get_valid_reset(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db() as conn:
        return conn.execute(
            "SELECT * FROM password_resets WHERE token_hash = ? AND used = 0 AND expires_at > ?",
            (token_hash, now),
        ).fetchone()


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()
    with db() as conn:
        user = conn.execute("SELECT id, email FROM users WHERE email = ?", (email,)).fetchone()

        if user:
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires = (datetime.now() + timedelta(minutes=RESET_TOKEN_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("DELETE FROM password_resets WHERE user_id = ? AND used = 0", (user["id"],))
            conn.execute(
                "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
                (user["id"], token_hash, expires),
            )
            link = f"{APP_BASE_URL}/reset-password/{token}"
            threading.Thread(target=send_reset_email, args=(user["email"], link), daemon=True).start()

    # Same message whether or not the email exists (so nobody can probe for accounts)
    flash("If that email is registered, a reset link has been sent. "
          "(No email set up? Check the server terminal for the link.)", "info")
    return redirect(url_for("login"))


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset = get_valid_reset(token)
    if reset is None:
        flash("This reset link is invalid or has expired. Please request a new one.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "GET":
        return render_template("reset_password.html", token=token)

    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return render_template("reset_password.html", token=token), 400
    if password != confirm:
        flash("Passwords do not match.", "danger")
        return render_template("reset_password.html", token=token), 400

    with db() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (generate_password_hash(password), reset["user_id"]))
        conn.execute("UPDATE password_resets SET used = 1 WHERE user_id = ?", (reset["user_id"],))

    flash("Password changed! Please log in with your new password.", "success")
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/video")
@api_login_required
def video():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/alarm")
@api_login_required
def alarm():
    alarm_on = time.time() <= alarm_until
    return jsonify({
        "animal_detected": animal_detected,
        "alarm_on": alarm_on,
        "play_alarm": alarm_on,
        "alarm_event_id": alarm_event_id,
        "labels": current_active_labels,
    })


@app.route("/advice")
@api_login_required
def advice():
    labels = list(current_active_labels)
    if labels:
        animal = labels[0]
        return jsonify({"animal": animal,
                        "info": get_chat_response(animal),
                        "tips": get_advice(animal)})
    return jsonify({"animal": "None", "info": "No animal detected", "tips": []})


@app.route("/chat", methods=["POST"])
@api_login_required
def chat():
    data = request.get_json(silent=True) or {}
    msg = str(data.get("message", "")).strip()

    reply = get_chat_response(msg)
    # If the typed message names no animal, fall back to the animal on camera.
    if reply == FALLBACK_REPLY and current_active_labels:
        reply = get_chat_response(current_active_labels[0])
    return jsonify({"reply": reply})


@app.route("/acknowledge", methods=["POST"])
@api_login_required
def acknowledge():
    with alerts_lock:
        for a in alerts_history:
            if a.get("status") == "Active":
                a["status"] = "Handled"
        save_alerts()
    return jsonify({"status": "acknowledged"})


# ---------------- RUN ---------------- #
if __name__ == "__main__":
    threading.Thread(target=camera_loop, daemon=True).start()
    print(f"🚀 Server running → http://{HOST}:{PORT}")
    try:
        # debug=False on purpose: debug mode + host 0.0.0.0 exposes a remote code console
        app.run(debug=False, host=HOST, port=PORT, threaded=True, use_reloader=False)
    finally:
        cap.release()
        print("📷 Camera released")
