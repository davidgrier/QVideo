from QVideo.lib import (QCamera, QVideoSource)
from PyQt5.QtCore import pyqtProperty
import numpy as np
from typing import Tuple


class QNoiseSource(QVideoSource):
    def __init__(self, *args, **kwargs) -> None:
        camera = QNoiseCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


class QNoiseCamera(QCamera):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._width = 640
        self._height = 480

    def _initialize(self):
        self.rng = np.random.default_rng()
        return True

    def _deinitialize(self):
        pass

    def read(self) -> Tuple[bool, np.ndarray]:
        shape = (self._height, self._width)
        image = self.rng.integers(0, 255, shape, np.uint8)
        return True, image

    @pyqtProperty(int)
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        self._width = value
        self.shapeChanged.emit(self.shape)

    @pyqtProperty(int)
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        self._height = value
        self.shapeChanged.emit(self.shape)
