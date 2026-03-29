from QVideo.lib import QCamera, QVideoSource
from QVideo.lib.resolutions import configure
from pyqtgraph.Qt import QtCore
import cv2
import platform
import logging


logger = logging.getLogger(__name__)


__all__ = ['QOpenCVCamera', 'QOpenCVSource']

_FLIP: dict[tuple[bool, bool], int] = {
    (True,  False): 1,   # mirror only  → horizontal flip
    (False, True):  0,   # flip only    → vertical flip
    (True,  True): -1,  # both         → 180° rotation
}

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

    Resolution and frame rate are configured once at device open time
    via :func:`~QVideo.lib.resolutions.configure`.  Three modes are
    supported:

    - **Quality** (default): probes the device, selects the largest
      supported resolution, and sets *fps* (default 30 fps).
    - **Performance** (*fps* ``= None``): probes the device, selects the
      smallest supported resolution, and lets the driver maximize frame
      rate (slo-mo mode).
    - **Explicit** (*width* and *height* both given): applies the
      requested dimensions and *fps* directly.

    ``width`` and ``height`` are registered as writable properties so that
    :class:`~QVideo.lib.QResolutionControl.QResolutionControl` can apply
    runtime changes.  Because V4L2 only accepts format changes when no
    frames are in flight, callers must stop the video source before
    invoking :meth:`~QVideo.lib.QCamera.QCamera.set` for these properties
    (``QResolutionControl.apply()`` guarantees this).  The
    :class:`~QVideo.cameras.OpenCV.QOpenCVTree.QOpenCVTree` keeps them
    disabled in the parameter tree so they cannot be edited interactively.
    Transform properties (``mirrored``, ``flipped``) are registered
    immediately on construction.  Device properties (``color``, and any
    properties in :data:`_PROBED_PROPS` that the device supports) are
    registered inside :meth:`_initialize` once the capture device is
    open.

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
    width : int or None
        Desired frame width [pixels].  Must be paired with *height* for
        explicit mode.  ``None`` triggers auto-selection.  Default: ``None``.
    height : int or None
        Desired frame height [pixels].  Must be paired with *width* for
        explicit mode.  ``None`` triggers auto-selection.  Default: ``None``.
    fps : float or None
        Desired frame rate [fps].  ``None`` selects performance mode.
        Default: ``30.``.
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
                 width: int | None = None,
                 height: int | None = None,
                 fps: float | None = 30.,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraID = cameraID
        self._mirrored = bool(mirrored)
        self._flipped = bool(flipped)
        self._gray = bool(gray)
        self._configWidth = width
        self._configHeight = height
        self._configFps = fps
        self.registerProperty('mirrored', ptype=bool)
        self.registerProperty('flipped', ptype=bool)
        self.open()

    def _initialize(self) -> bool:
        '''Open the OpenCV VideoCapture device and register device properties.

        Configures resolution and frame rate via
        :func:`~QVideo.lib.resolutions.configure` using the values supplied
        at construction time.  Registers ``width`` and ``height`` as
        writable properties, ``color`` as read-write, then probes the
        device for each property in :data:`_PROBED_PROPS` and registers
        those it supports.

        Returns
        -------
        bool
            ``True`` if the device was opened and returned at least one frame.
        '''
        api = cv2.CAP_V4L2 if platform.system() == 'Linux' else cv2.CAP_ANY
        self.device = cv2.VideoCapture(self.cameraID, api)
        configure(self.device, self._configWidth, self._configHeight,
                  self._configFps)
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
            self.shapeChanged.emit(self.shape)
        else:
            self.device.release()
        return ready

    def _probeProperties(self) -> None:
        '''Register device properties that the camera actually supports.

        For each entry in :data:`_PROBED_PROPS`, attempts to set the
        property to its current value.  If the device accepts the write,
        the property is registered as read-write; otherwise it is skipped.
        '''
        registered = []
        for name, (prop_id, ptype) in _PROBED_PROPS.items():
            value = self.device.get(prop_id)
            if self.device.set(prop_id, value):
                setter = (self._setFps if name == 'fps'
                          else lambda v, p=prop_id: self.device.set(p, v))
                self.registerProperty(
                    name,
                    getter=lambda p=prop_id, t=ptype: t(self.device.get(p)),
                    setter=setter,
                    ptype=ptype)
                registered.append(name)
            else:
                logger.debug(f'Property {name!r} not supported by this device')
        logger.debug(
            f'Registered {len(registered)} device properties: {registered}')

    def _deinitialize(self) -> None:
        '''Release the OpenCV VideoCapture device.'''
        self.device.release()

    def _getWidth(self) -> int:
        return int(self.device.get(self.WIDTH))

    def _setWidth(self, value: int) -> None:
        '''Store the requested width so the next :meth:`_initialize` applies it.

        Resolution changes require a full device close/reopen cycle
        (V4L2 ``VIDIOC_S_FMT`` is only reliable before streaming starts).
        Updating :attr:`_configWidth` here means that when
        :class:`~QVideo.lib.QResolutionControl.QResolutionControl` restarts
        the source, :meth:`_initialize` will call
        :func:`~QVideo.lib.resolutions.configure` with the new value.
        '''
        self._configWidth = int(value)

    def _getHeight(self) -> int:
        return int(self.device.get(self.HEIGHT))

    def _setHeight(self, value: int) -> None:
        '''Store the requested height so the next :meth:`_initialize` applies it.

        See :meth:`_setWidth` for rationale.
        '''
        self._configHeight = int(value)

    def _setFps(self, value: float) -> None:
        '''Store the requested frame rate and apply it to the open device.

        Unlike width/height, frame-rate changes in V4L2 do not require
        stopping the stream, so the value is written to the device
        immediately as well as stored for the next :meth:`_initialize`.
        '''
        self._configFps = float(value)
        self.device.set(self.FPS, self._configFps)

    def _getColor(self) -> bool:
        '''Return color mode
            ``True`` if frames are delivered in color
            ``False`` for grayscale.'''
        return not self._gray

    def _setColor(self, value: bool) -> None:
        '''Set color mode.
            ``False`` converts frames to grayscale
            ``True`` restores color.'''
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
            try:
                ready, image = self.device.read()
            except Exception as e:
                logger.warning(f'Frame read failed: {e}')
                return False, None
        else:
            return False, None
        if ready:
            if image.ndim == 3:
                code = self.BGR2GRAY if self._gray else self.BGR2RGB
                image = cv2.cvtColor(image, code)
            if self._flipped or self._mirrored:
                operation = _FLIP[(self._mirrored, self._flipped)]
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
