from QVideo.lib import QCamera, QVideoSource
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
        Minimum pixel value (inclusive). Default: ``48``.
    whitelevel : int
        Maximum pixel value (exclusive). Default: ``128``.
    *args :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    '''

    def __init__(self, *args,
                 blacklevel: int = 48,
                 whitelevel: int = 128,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._width = 640
        self._height = 480
        self._fps = 30.
        self._blacklevel = int(np.clip(blacklevel, 0, 254))
        self._whitelevel = int(np.clip(whitelevel, 1, 255))

        register = self.registerProperty
        register('width', setter=self._setWidth, ptype=int)
        register('height', setter=self._setHeight, ptype=int)
        register('fps', ptype=float)
        register('color', getter=lambda: False, setter=None, ptype=bool)
        register('blacklevel', setter=self._setBlacklevel, ptype=int)
        register('whitelevel', setter=self._setWhitelevel, ptype=int)
        self.open()

    def _setWidth(self, value: int) -> None:
        '''Set frame width and emit :attr:`shapeChanged`.'''
        self._width = int(value)
        self.shapeChanged.emit(self.shape)

    def _setHeight(self, value: int) -> None:
        '''Set frame height and emit :attr:`shapeChanged`.'''
        self._height = int(value)
        self.shapeChanged.emit(self.shape)

    def _setBlacklevel(self, value: int) -> None:
        '''Set black level, clamped to [0, 254].

        Rejects values that would make blacklevel >= whitelevel.
        '''
        value = int(np.clip(value, 0, 254))
        if value >= self._whitelevel:
            logger.warning(
                f'blacklevel {value} must be less than '
                f'whitelevel {self._whitelevel}: ignoring')
            return
        self._blacklevel = value

    def _setWhitelevel(self, value: int) -> None:
        '''Set white level, clamped to [1, 255].

        Rejects values that would make whitelevel <= blacklevel.
        '''
        value = int(np.clip(value, 1, 255))
        if value <= self._blacklevel:
            logger.warning(
                f'whitelevel {value} must be greater than '
                f'blacklevel {self._blacklevel}: ignoring')
            return
        self._whitelevel = value

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
        '''Release the random number generator.'''
        self._rng = None

    def read(self) -> QCamera.CameraData:
        '''Generate and return a random noise frame.

        Returns
        -------
        tuple[bool, ndarray]
            ``(True, frame)`` where ``frame`` is a grayscale uint8 array
            of shape ``(height, width)``.
        '''
        if not self.isOpen():
            return False, None
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
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QNoiseCamera.example()
