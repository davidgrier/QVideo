from QVideo.lib import (QCamera, QVideoSource)
from PyQt5.QtCore import pyqtProperty
import numpy as np
import time


class QNoiseSource(QVideoSource):
    def __init__(self, *args, **kwargs) -> None:
        camera = QNoiseCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


class QNoiseCamera(QCamera):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._width = 640
        self._height = 480
        self._fps = 30.
        self.open()

    def _initialize(self):
        self.rng = np.random.default_rng()
        return True

    def _deinitialize(self):
        pass

    def read(self) -> QCamera.CameraData:
        time.sleep(self.delay())
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

    @pyqtProperty(float)
    def fps(self) -> float:
        return self._fps

    @fps.setter
    def fps(self, fps: float) -> None:
        self._fps = fps

    def delay(self) -> float:
        return 1./self.fps


if __name__ == '__main__':
    QNoiseCamera.example()
