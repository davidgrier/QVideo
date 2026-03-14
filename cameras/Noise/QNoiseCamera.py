from QVideo.lib import QCamera, QVideoSource
from pyqtgraph.Qt import QtCore
import numpy as np
import time
import logging


logger = logging.getLogger(__name__)


__all__ = ['QNoiseCamera', 'QNoiseSource']


class QNoiseCamera(QCamera):

    '''Camera that generates random noise frames.

    Useful for testing and development without physical camera hardware.
    All properties are registered on construction; the camera opens
    automatically.

    Parameters
    ----------
    blacklevel : int
        Minimum pixel value (inclusive). Default: ``0``.
    whitelevel : int
        Maximum pixel value (exclusive). Default: ``255``.
    *args :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    '''

    def __init__(self, *args,
                 blacklevel: int = 0,
                 whitelevel: int = 255,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._width = 640
        self._height = 480
        self._fps = 30.
        self._blacklevel = int(np.clip(blacklevel, 0, 254))
        self._whitelevel = int(np.clip(whitelevel, 1, 255))

        self.registerProperty('width',
                              getter=lambda: self._width,
                              setter=self._setWidth,
                              ptype=int)
        self.registerProperty('height',
                              getter=lambda: self._height,
                              setter=self._setHeight,
                              ptype=int)
        self.registerProperty('fps',
                              getter=lambda: self._fps,
                              setter=lambda v: setattr(self, '_fps', float(v)),
                              ptype=float)
        self.registerProperty('color',
                              getter=lambda: False,
                              ptype=bool)
        self.registerProperty('blacklevel',
                              getter=lambda: self._blacklevel,
                              setter=lambda v: setattr(
                                  self, '_blacklevel', int(np.clip(v, 0, 254))),
                              ptype=int)
        self.registerProperty('whitelevel',
                              getter=lambda: self._whitelevel,
                              setter=lambda v: setattr(
                                  self, '_whitelevel', int(np.clip(v, 1, 255))),
                              ptype=int)
        self.open()

    def _setWidth(self, value: int) -> None:
        self._width = int(value)
        self.shapeChanged.emit(self.shape)

    def _setHeight(self, value: int) -> None:
        self._height = int(value)
        self.shapeChanged.emit(self.shape)

    def _initialize(self) -> bool:
        '''Seed the random number generator.

        Returns
        -------
        bool
            Always ``True``.
        '''
        self._rng = np.random.default_rng()
        return True

    def _deinitialize(self) -> None:
        pass

    def read(self) -> QCamera.CameraData:
        '''Generate and return a random noise frame.

        Returns
        -------
        tuple[bool, ndarray]
            ``(True, frame)`` where ``frame`` is a grayscale uint8 array
            of shape ``(height, width)``.
        '''
        time.sleep(1. / self._fps)
        image = self._rng.integers(self._blacklevel, self._whitelevel,
                                   (self._height, self._width), np.uint8)
        return True, image


class QNoiseSource(QVideoSource):

    '''Threaded video source backed by :class:`QNoiseCamera`.

    Parameters
    ----------
    camera : QNoiseCamera or None
        Camera instance to wrap.  If ``None``, a new
        :class:`QNoiseCamera` is created from the remaining arguments.
    *args :
        Forwarded to :class:`QNoiseCamera` when ``camera`` is ``None``.
    **kwargs :
        Forwarded to :class:`QNoiseCamera` when ``camera`` is ``None``.
    '''

    def __init__(self, *args,
                 camera: QNoiseCamera | None = None,
                 **kwargs) -> None:
        camera = camera or QNoiseCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':  # pragma: no cover
    QNoiseCamera.example()
