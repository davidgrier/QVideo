from QVideoCamera import QVideoCamera
from PyQt5.QtCore import pyqtProperty
import numpy as np


class QNoiseSource(QVideoCamera):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = 640
        self.height = 480
        self.rng = np.random.default_rng()

    def read(self):
        image = self.rng.integers(0, 255, self.shape(), np.uint8)
        return True, image

    @pyqtProperty(int)
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value
        self.sizeChanged.emit()

    @pyqtProperty(int)
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value
        self.sizeChanged.emit()

    def shape(self):
        return (self.height, self.width)
