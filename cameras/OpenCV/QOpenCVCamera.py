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

    Properties
    ----------
    width : int
        Frame width in pixels.
    height : int
        Frame height in pixels.
    fps : float
        Capture frame rate.
    mirrored : bool
        Whether horizontal mirroring is active.
    flipped : bool
        Whether vertical flipping is active.
    gray : bool
        Whether grayscale conversion is active.
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
        self.open()
        self.mirrored = mirrored
        self.flipped = flipped
        self.gray = gray

    def _initialize(self) -> bool:
        '''Open the OpenCV VideoCapture device.

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
        return ready

    def _deinitialize(self) -> None:
        '''Release the OpenCV VideoCapture device.'''
        self.device.release()

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
                code = self.BGR2GRAY if self.gray else self.BGR2RGB
                image = cv2.cvtColor(image, code)
            if self.flipped or self.mirrored:
                operation = self.mirrored * (1 - 2 * self.flipped)
                image = cv2.flip(image, operation)
        return ready, image

    @QtCore.pyqtProperty(int)
    def width(self) -> int:
        '''Frame width in pixels.'''
        return int(self.device.get(self.WIDTH))

    @width.setter
    def width(self, value: int) -> None:
        self.device.set(self.WIDTH, value)
        self.shapeChanged.emit(self.shape)

    @QtCore.pyqtProperty(int)
    def height(self) -> int:
        '''Frame height in pixels.'''
        return int(self.device.get(self.HEIGHT))

    @height.setter
    def height(self, value: int) -> None:
        self.device.set(self.HEIGHT, value)
        self.shapeChanged.emit(self.shape)

    @QtCore.pyqtProperty(float)
    def fps(self) -> float:
        '''Capture frame rate in frames per second.'''
        return float(self.device.get(self.FPS))

    @fps.setter
    def fps(self, value: float) -> None:
        self.device.set(self.FPS, value)

    @QtCore.pyqtProperty(bool)
    def color(self) -> bool:
        '''``True`` if the camera delivers colour frames.'''
        return not self.gray

    @QtCore.pyqtProperty(bool)
    def mirrored(self) -> bool:
        '''``True`` if frames are flipped horizontally.'''
        return self._mirrored

    @mirrored.setter
    def mirrored(self, value: bool) -> None:
        self._mirrored = bool(value)

    @QtCore.pyqtProperty(bool)
    def flipped(self) -> bool:
        '''``True`` if frames are flipped vertically.'''
        return self._flipped

    @flipped.setter
    def flipped(self, value: bool) -> None:
        self._flipped = bool(value)

    @QtCore.pyqtProperty(bool)
    def gray(self) -> bool:
        '''``True`` if frames are converted to grayscale.'''
        return self._gray

    @gray.setter
    def gray(self, value: bool) -> None:
        self._gray = bool(value)


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
