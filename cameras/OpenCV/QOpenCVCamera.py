from QVideo.lib import QCamera, QVideoSource
from pyqtgraph.Qt import QtCore
import cv2
import platform
import logging


logger = logging.getLogger(__name__)


__all__ = ['QOpenCVCamera', 'QOpenCVSource']


class QOpenCVCamera(QCamera):

    '''Camera backed by OpenCV's ``VideoCapture``.

    Supports USB webcams and any device accessible via OpenCV.
    On Linux the V4L2 backend is selected automatically; all other
    platforms use ``CAP_ANY``.

    Transform properties (``mirrored``, ``flipped``, ``gray``) are
    registered immediately on construction.  Device properties
    (``width``, ``height``, ``fps``, ``color``) are registered inside
    :meth:`_initialize` once the capture device is open.

    Parameters
    ----------
    cameraID : int
        Index of the camera device to open. Default: ``0``.
    mirrored : bool
        Flip the image horizontally. Default: ``False``.
    flipped : bool
        Flip the image vertically. Default: ``False``.
    gray : bool
        Convert frames to grayscale. Default: ``False``.
    *args :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    '''

    WIDTH = cv2.CAP_PROP_FRAME_WIDTH
    HEIGHT = cv2.CAP_PROP_FRAME_HEIGHT
    FPS = cv2.CAP_PROP_FPS
    BGR2RGB = cv2.COLOR_BGR2RGB
    BGR2GRAY = cv2.COLOR_BGR2GRAY

    def __init__(self, *args,
                 cameraID: int = 0,
                 mirrored: bool = False,
                 flipped: bool = False,
                 gray: bool = False,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraID = cameraID
        self._mirrored = bool(mirrored)
        self._flipped = bool(flipped)
        self._gray = bool(gray)
        self.registerProperty('mirrored', ptype=bool)
        self.registerProperty('flipped', ptype=bool)
        self.registerProperty('gray', ptype=bool)
        self.open()

    def _initialize(self) -> bool:
        '''Open the OpenCV VideoCapture device and register device properties.

        Returns
        -------
        bool
            ``True`` if the device was opened and returned at least one frame.
        '''
        api = cv2.CAP_V4L2 if platform.system() == 'Linux' else cv2.CAP_ANY
        self.device = cv2.VideoCapture(self.cameraID, api)
        for _ in range(5):
            if (ready := self.device.read()[0]):
                break
        if ready:
            self.registerProperty('width',
                                  getter=lambda: int(self.device.get(self.WIDTH)),
                                  setter=self._setWidth,
                                  ptype=int)
            self.registerProperty('height',
                                  getter=lambda: int(self.device.get(self.HEIGHT)),
                                  setter=self._setHeight,
                                  ptype=int)
            self.registerProperty('fps',
                                  getter=lambda: float(self.device.get(self.FPS)),
                                  setter=lambda v: self.device.set(self.FPS, v),
                                  ptype=float)
            self.registerProperty('color',
                                  getter=lambda: not self._gray,
                                  setter=None, ptype=bool)
        return ready

    def _deinitialize(self) -> None:
        '''Release the OpenCV VideoCapture device.'''
        self.device.release()

    def _setWidth(self, value: int) -> None:
        self.device.set(self.WIDTH, value)
        self.shapeChanged.emit(self.shape)

    def _setHeight(self, value: int) -> None:
        self.device.set(self.HEIGHT, value)
        self.shapeChanged.emit(self.shape)

    def read(self) -> QCamera.CameraData:
        '''Read one frame from the camera.

        Applies colour conversion and geometric transforms according to
        the current ``gray``, ``mirrored``, and ``flipped`` settings.

        Returns
        -------
        tuple[bool, ndarray or None]
            ``(True, frame)`` on success, ``(False, None)`` when closed.
        '''
        if self.isOpen():
            ready, image = self.device.read()
        else:
            return False, None
        if ready:
            if image.ndim == 3:
                code = self.BGR2GRAY if self._gray else self.BGR2RGB
                image = cv2.cvtColor(image, code)
            if self._flipped or self._mirrored:
                operation = self._mirrored * (1 - 2 * self._flipped)
                image = cv2.flip(image, operation)
        return ready, image


class QOpenCVSource(QVideoSource):

    '''Threaded video source backed by :class:`QOpenCVCamera`.

    Parameters
    ----------
    camera : QOpenCVCamera or None
        Camera instance to wrap. If ``None``, a new :class:`QOpenCVCamera`
        is created from the remaining arguments.
    *args :
        Forwarded to :class:`QOpenCVCamera` when ``camera`` is ``None``.
    **kwargs :
        Forwarded to :class:`QOpenCVCamera` when ``camera`` is ``None``.
    '''

    def __init__(self, *args,
                 camera: QOpenCVCamera | None = None,
                 **kwargs) -> None:
        camera = camera or QOpenCVCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':  # pragma: no cover
    QOpenCVCamera.example()
