from ultralytics import YOLO
from pyqtgraph.Qt import QtCore
from QVideo.lib.types import Image
import numpy as np


class YoloOverlay:
    def __init__(self, model_path: str = 'yolov26n.pt'):
        self.model = YOLO(model_path)

    @QtCore.pyqtSlot(np.ndarray)
    def predict(self, frame: np.ndarray) -> None:
        results = self.model.predict(frame, stream=True)
        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()
            for box, score, cls in zip(boxes, scores, classes):
                x1, y1, x2, y2 = box.astype(int)
                print(
                    f'Class: {cls}, Score: {score:.2f}, Box: ({x1}, {y1}), ({x2}, {y2})')
