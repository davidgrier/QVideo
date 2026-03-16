from QVideo.lib import QCamera, QVideoSource
from pyqtgraph.Qt import QtCore
import cv2
import platform
import logging


logger = logging.getLogger(__name__)


__all__ = ['QOpenCVCamera', 'QOpenCVSource']


# Curated set of device properties to probe at runtime.
# Maps display name → (CAP_PROP_* id, Python type).
# Width, height, and color are handled separately.
_PROBED_PROPS: dict[str, tuple[int, type]] = {
    'fps':        (cv2.CAP_PROP_FPS,         float),
    'brightness': (cv2.CAP_PROP_BRIGHTNESS,  float),
    'contrast':   (cv2.CAP_PROP_CONTRAST,    float),
    'saturation': (cv2.CAP_PROP_SATURATION,  float),
    'hue':        (cv2.CAP_PROP_HUE,         float),
    'gain':       (cv2.CAP_PROP_GAIN,        float),
    'exposure':   (cv2.CAP_PROP_EXPOSURE,    float),
    'sharpness':  (cv2.CAP_PROP_SHARPNESS,   float),
    'gamma':      (cv2.CAP_PROP_GAMMA,       float),
    'backlight':  (cv2.CAP_PROP_BACKLIGHT,   float),
    'focus':      (cv2.CAP_PROP_FOCUS,       float),
    'zoom':       (cv2.CAP_PROP_ZOOM,        float),
}


class QOpenCVCamera(QCamera):

    '''Camera backed by OpenCV's ``VideoCapture``.

    Supports USB webcams and any device accessible via OpenCV.
    On Linux the V4L2 backend is selected automatically; all other
    platforms use ``CAP_ANY``.

    Transform properties (``mirrored``, ``flipped``) are registered
    immediately on construction.  Device properties (``width``,
    ``height``, ``color``, and any properties in :data:`_PROBED_PROPS`
    that the device supports) are registered inside :meth:`_initialize`
    once the capture device is open.

    Parameters
    ----------
    cameraID : int
        Index of the camera device to open. Default: ``0``.
    mirrored : bool
        Flip the image horizontally. Default: ``False``.
    flipped : bool
        Flip the image vertically. Default: ``False``.
    gray : bool
        Initial grayscale state.  Equivalent to opening with ``color=False``.
        Default: ``False`` (color output).
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
        self.open()

    def _initialize(self) -> bool:
        '''Open the OpenCV VideoCapture device and register device properties.

        Registers ``width``, ``height``, and ``color`` unconditionally,
        then probes the device for each property in :data:`_PROBED_PROPS`
        and registers those it supports.

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
            self.registerProperty('width', getter=self._getWidth,
                                  setter=self._setWidth, ptype=int)
            self.registerProperty('height', getter=self._getHeight,
                                  setter=self._setHeight, ptype=int)
            self.registerProperty('color', getter=self._getColor,
                                  setter=self._setColor, ptype=bool)
            self._probeProperties()
        return ready

    def _probeProperties(self) -> None:
        '''Register device properties that the camera actually supports.

        For each entry in :data:`_PROBED_PROPS`, attempts to set the
        property to its current value.  If the device accepts the write,
        the property is registered as read-write; otherwise it is skipped.
        '''
        for name, (prop_id, ptype) in _PROBED_PROPS.items():
            value = self.device.get(prop_id)
            if self.device.set(prop_id, value):
                self.registerProperty(
                    name,
                    getter=lambda p=prop_id, t=ptype: t(self.device.get(p)),
                    setter=lambda v, p=prop_id: self.device.set(p, v),
                    ptype=ptype)
                logger.debug(f'Registered property: {name!r}')
            else:
                logger.debug(f'Property {name!r} not supported by this device')

    def _deinitialize(self) -> None:
        '''Release the OpenCV VideoCapture device.'''
        self.device.release()

    def _getWidth(self) -> int:
        return int(self.device.get(self.WIDTH))

    def _setWidth(self, value: int) -> None:
        self.device.set(self.WIDTH, value)
        self.shapeChanged.emit(self.shape)

    def _getHeight(self) -> int:
        return int(self.device.get(self.HEIGHT))

    def _setHeight(self, value: int) -> None:
        self.device.set(self.HEIGHT, value)
        self.shapeChanged.emit(self.shape)

    def _getColor(self) -> bool:
        '''Return ``True`` if frames are delivered in color, ``False`` for grayscale.'''
        return not self._gray

    def _setColor(self, value: bool) -> None:
        '''Set color mode.  ``False`` converts frames to grayscale; ``True`` restores color.'''
        self._gray = not bool(value)

    def read(self) -> QCamera.CameraData:
        '''Read one frame from the camera.

        Applies color conversion and geometric transforms according to
        the current ``color``, ``mirrored``, and ``flipped`` settings.

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
        if camera is None:
            camera = QOpenCVCamera(*args, **kwargs)
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QOpenCVCamera.example()
