"""Stand-alone webcam test (no Flask). Press Q to quit.  Run: python detect.py"""
import cv2
from ultralytics import YOLO

model = YOLO("yolov8s.pt")
ANIMALS = {"elephant", "bear", "zebra", "giraffe"}  # wild animals in COCO
# ("cow", "horse", "sheep" are farm animals - add them back if you want them)


def detect_frame(frame, conf_threshold=0.55):
    labels = []
    for r in model(frame, conf=conf_threshold, iou=0.5, imgsz=640, verbose=False):
        for box in r.boxes:
            label = model.names[int(box.cls[0])]
            if label not in ANIMALS:
                continue
            conf = float(box.conf[0])
            if label not in labels:
                labels.append(label)
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            text = f"{label.upper()} {conf * 100:.1f}%"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 10, y1), (0, 0, 255), -1)
            cv2.putText(frame, text, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 255, 255), 2)
    return frame, bool(labels), labels


if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        frame, detected, labels = detect_frame(frame)
        cv2.imshow("Detect (Q to quit)", frame)
        if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
            break
    cap.release()
    cv2.destroyAllWindows()
