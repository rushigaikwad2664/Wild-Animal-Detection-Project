import os
import sys

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alarm.wav")

if not os.path.exists(path):
    sys.exit(f"alarm.wav not found at {path}")

if sys.platform.startswith("win"):
    import winsound
    winsound.PlaySound(path, winsound.SND_FILENAME)
else:
    print("winsound works on Windows only. The web app plays the alarm in the browser.")
