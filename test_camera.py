import sys

import cv2

for i in range(5):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) if sys.platform.startswith("win") else cv2.VideoCapture(i)
    ok = cap.isOpened() and cap.read()[0]
    print(f"Camera {i} working:", ok)
    cap.release()
