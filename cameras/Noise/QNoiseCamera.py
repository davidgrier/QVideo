from QVideo.lib import (QCamera, QVideoSource)
from pyqtgraph.Qt.QtCore import pyqtProperty
import numpy as np
import time


__all__ = ['QNoiseCamera', 'QNoiseSource']


class QNoiseCamera(QCamera):
    '''A camera that generates random noise images.

    Emits frames of random noise at a specified resolution and frame rate.

    Inherits
    --------
    QCamera
        Base camera class providing camera functionality.

    Properties
    ----------
    width : int
        The width of the generated images in pixels.
    height : int
        The height of the generated images in pixels.
    fps : float
        The frame rate at which images are generated.
    shape : tuple
        The shape of the generated images as (height, width).

    Methods
    -------
    read() -> QCamera.CameraData
        Generates and returns a frame of random noise.

    Signals
    -------
    shapeChanged
        Emitted when the shape of the generated images changes.
    '''

    def __init__(self, *args,
                 blackLevel: int = 0,
                 whiteLevel: int = 255,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.blackLevel = blackLevel
        self.whiteLevel = whiteLevel
        self._width = 640
        self._height = 480
        self._fps = 30.
        self.open()

    def _initialize(self):
        self._rng = np.random.default_rng()
        return True

    def _deinitialize(self):
        pass

    def read(self) -> QCamera.CameraData:
        time.sleep(1./self.fps)
        shape = (self._height, self._width)
        image = self._rng.integers(self.blackLevel,
                                   self.whiteLevel,
                                   shape, np.uint8)
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

    @pyqtProperty(int)
    def blackLevel(self) -> int:
        return self._blackLevel

    @blackLevel.setter
    def blackLevel(self, level: int) -> None:
        self._blackLevel = np.clip(level, 0, 254)

    @pyqtProperty(int)
    def whiteLevel(self) -> int:
        return self._whiteLevel

    @whiteLevel.setter
    def whiteLevel(self, level: int) -> None:
        self._whiteLevel = np.clip(level, 1, 255)


class QNoiseSource(QVideoSource):

    '''Threaded video source that generates random noise images.

    Inherits
    --------
    QVideoSource
        Base video source class providing threading and frame delivery.

    Parameters
    ----------
    camera : QNoiseCamera | None
        An instance of QNoiseCamera. If None, a new instance is created.
    '''

    def __init__(self, *args,
                 camera: QNoiseCamera | None = None,
                 **kwargs) -> None:
        camera = camera or QNoiseCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':
    QNoiseCamera.example()
