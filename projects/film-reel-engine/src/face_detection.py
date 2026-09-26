from __future__ import annotations
import cv2
import numpy as np


class FaceDetector:
    def __init__(self) -> None:
        self.model = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        if self.model.empty():
            raise RuntimeError('OpenCV frontal-face cascade is unavailable')

    def detect(self, frame: np.ndarray) -> list[list[float]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        boxes = self.model.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(24, 24))
        return [[float(x / w), float(y / h), float(bw / w), float(bh / h)] for x, y, bw, bh in boxes]
