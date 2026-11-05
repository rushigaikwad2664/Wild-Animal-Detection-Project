from multiprocessing import freeze_support

from ultralytics import YOLO

if __name__ == "__main__":
    freeze_support()  # needed on Windows
    model = YOLO("yolov8n.pt")
    model.train(
        data="data.yaml",   # edit the 'path:' line inside data.yaml first
        epochs=50,
        imgsz=640,
        batch=16,
        name="train3",
        workers=0,          # avoids multiprocessing errors on Windows
    )
    # Result: runs/detect/train3/weights/best.pt
