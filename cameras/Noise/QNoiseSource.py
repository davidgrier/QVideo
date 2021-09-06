from QVideo.lib import QVideoCamera
from PyQt5.QtCore import pyqtProperty
import numpy as np


class QNoiseSource(QVideoCamera):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._width = 640
        self._height = 480
        self.rng = np.random.default_rng()

    def read(self):
        shape = (self._height, self._width)
        image = self.rng.integers(0, 255, shape, np.uint8)
        return True, image

    @pyqtProperty(int)
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value
        self.shapeChanged.emit()

    @pyqtProperty(int)
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value
        self.shapeChanged.emit()
