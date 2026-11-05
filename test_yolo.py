import sys

from ultralytics import YOLO

image = sys.argv[1] if len(sys.argv) > 1 else "test_image.jpg"
model = YOLO("yolov8n.pt")
results = model(image)
results[0].show()   # results is a list, so take [0]
