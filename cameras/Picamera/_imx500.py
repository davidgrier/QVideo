from typing import TYPE_CHECKING
from qtpy import QtCore
from QVideo.lib import QVideoSource
from ._camera import QPicamera
import logging

if TYPE_CHECKING:
    from picamera2.devices.imx500 import IMX500 as _IMX500

try:
    from picamera2.devices.imx500 import IMX500
except (ImportError, ModuleNotFoundError):
    IMX500 = None


logger = logging.getLogger(__name__)

__all__ = ['QIMXCamera', 'QIMXSource']


class QIMXCamera(QPicamera):

    '''Raspberry Pi AI Camera (IMX500) with on-sensor neural-network inference.

    Extends :class:`~QVideo.cameras.Picamera.QPicamera` to drive the IMX500
    sensor\'s on-chip AI accelerator.  Each captured frame is accompanied by
    raw inference outputs, emitted via :attr:`newOutput`.  Callers — overlays,
    analysis widgets, or application code — connect to :attr:`newOutput` and
    interpret the tensors for their specific model.

    Requires ``picamera2 >= 0.3.20`` with IMX500 support::

        pip install "picamera2[imx500]"

    Parameters
    ----------
    model : str
        Path to the packed-network file (``.rpk``) to load onto the sensor.
    cameraID : int
        Index of the camera.  Default: ``0``.
    width : int
        Initial frame width in pixels.  Default: ``1280``.
    height : int
        Initial frame height in pixels.  Default: ``960``.
    gray : bool
        ``True`` to deliver grayscale frames.  Default: ``False``.
    hflip : bool
        ``True`` to mirror frames horizontally.  Default: ``False``.
    vflip : bool
        ``True`` to flip frames vertically.  Default: ``False``.

    Signals
    -------
    newOutput : list[numpy.ndarray] or None
        Emitted alongside each frame with the raw inference output tensors.
        The tensor structure depends on the loaded network model.  ``None``
        is emitted when the sensor has not yet produced outputs (e.g. on the
        first few frames after start-up).
    '''

    #: Raw IMX500 inference outputs, emitted once per frame.
    newOutput = QtCore.Signal(object)

    def __init__(self, *args, model: str, **kwargs) -> None:
        self._model = model
        super().__init__(*args, **kwargs)

    def _createDevice(self) -> '_IMX500 | None':
        '''Return an :class:`~picamera2.devices.imx500.IMX500` instance.

        Returns ``None`` when ``picamera2.devices.imx500`` is unavailable.
        '''
        if IMX500 is None:
            logger.warning(
                'picamera2.devices.imx500 is not available. '
                'Install with: pip install "picamera2[imx500]"')
            return None
        return IMX500(self._model, camera_num=self._cameraID)

    def _onRequest(self, metadata: dict) -> None:
        '''Extract IMX500 inference outputs and emit :attr:`newOutput`.

        Parameters
        ----------
        metadata : dict
            Frame metadata from :meth:`~picamera2.Picamera2.capture_request`.
        '''
        outputs = self._device.get_outputs(metadata)
        self.newOutput.emit(outputs)


class QIMXSource(QVideoSource):

    '''Threaded video source backed by :class:`QIMXCamera`.

    Parameters
    ----------
    camera : QIMXCamera or None
        Camera instance to wrap.  If ``None``, a new :class:`QIMXCamera`
        is created from the remaining arguments.
    *args :
        Forwarded to :class:`QIMXCamera` when *camera* is ``None``.
    **kwargs :
        Forwarded to :class:`QIMXCamera` when *camera* is ``None``.
    '''

    def __init__(self, *args,
                 camera: QIMXCamera | None = None,
                 **kwargs) -> None:
        camera = camera if camera is not None else QIMXCamera(*args, **kwargs)
        super().__init__(camera)
