from QVideo.lib import QCamera, QVideoSource
import logging

try:
    from picamera2 import Picamera2
except (ImportError, ModuleNotFoundError):
    Picamera2 = None


logger = logging.getLogger(__name__)


__all__ = ['QPicamera', 'QPicameraSource']


# picamera2 control names and their Python types.
# Only controls listed here are probed and registered as properties.
_CONTROL_TYPES: dict[str, type] = {
    'AeEnable':     bool,
    'AwbEnable':    bool,
    'Brightness':   float,
    'Contrast':     float,
    'Saturation':   float,
    'Sharpness':    float,
    'ExposureTime': int,
    'AnalogueGain': float,
}


class QPicamera(QCamera):

    '''Camera backed by the Raspberry Pi camera module via picamera2.

    Supports all CSI-connected camera modules on a Raspberry Pi SBC,
    including the HQ Camera, Camera Module 3, and similar sensors.
    Frames are delivered as RGB arrays.

    Requires the ``picamera2`` package, which is pre-installed on
    Raspberry Pi OS.  Install manually with::

        pip install picamera2

    Parameters
    ----------
    cameraID : int
        Index of the camera to open when multiple modules are attached.
        Default: ``0``.
    width : int
        Initial frame width in pixels.  Default: ``1280``.
    height : int
        Initial frame height in pixels.  Default: ``960``.
    *args :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    '''

    def __init__(self, *args,
                 cameraID: int = 0,
                 width: int = 1280,
                 height: int = 960,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraID = cameraID
        self._width = int(width)
        self._height = int(height)
        self._controlValues: dict = {}
        self.open()

    def _initialize(self) -> bool:
        '''Open the Raspberry Pi camera and register available controls.

        Returns
        -------
        bool
            ``True`` if the camera was opened and delivering frames.
        '''
        if Picamera2 is None:
            logger.warning(
                'picamera2 is not available. '
                'Install it on Raspberry Pi with: pip install picamera2')
            return False
        try:
            self.device = Picamera2(camera_num=self.cameraID)
        except Exception as ex:
            logger.warning(
                f'Could not open Raspberry Pi camera {self.cameraID}: {ex}')
            return False
        config = self.device.create_preview_configuration(
            main={'size': (self._width, self._height), 'format': 'RGB888'})
        self.device.configure(config)
        self.device.start()
        try:
            self.device.capture_array()
        except Exception as ex:
            logger.warning(f'Camera did not deliver a frame: {ex}')
            self.device.stop()
            self.device.close()
            return False
        self.registerProperty('width', getter=self._getWidth,
                              setter=self._setWidth, ptype=int)
        self.registerProperty('height', getter=self._getHeight,
                              setter=self._setHeight, ptype=int)
        self.registerProperty('color', getter=lambda: True,
                              setter=None, ptype=bool)
        metadata = self.device.capture_metadata()
        self._probeControls(metadata)
        self._registerFrameRate(metadata)
        return True

    def _probeControls(self, metadata: dict) -> None:
        '''Register picamera2 controls supported by this camera.

        For each name in :data:`_CONTROL_TYPES` that the camera reports in
        :attr:`~picamera2.Picamera2.camera_controls`, a read-write property
        is registered with the hardware-reported range.

        Parameters
        ----------
        metadata : dict
            Frame metadata from :meth:`~picamera2.Picamera2.capture_metadata`,
            used to initialise cached control values.
        '''
        for name, ptype in _CONTROL_TYPES.items():
            if name not in self.device.camera_controls:
                continue
            lo, hi, default = self.device.camera_controls[name]
            current = metadata.get(name, default)
            self._controlValues[name] = ptype(current)
            meta = {}
            if ptype is not bool:
                if lo is not None:
                    meta['minimum'] = lo
                if hi is not None:
                    meta['maximum'] = hi
            self.registerProperty(
                name,
                getter=lambda n=name, t=ptype: t(self._controlValues[n]),
                setter=lambda v, n=name, t=ptype: self._setControl(n, t(v)),
                ptype=ptype,
                **meta)

    def _registerFrameRate(self, metadata: dict) -> None:
        '''Register the ``fps`` property if the camera supports it.

        Frame rate is controlled via ``FrameDurationLimits``, a picamera2
        control that accepts a ``(min_µs, max_µs)`` tuple.  Setting both
        elements to the same value pins the frame rate.

        Parameters
        ----------
        metadata : dict
            Frame metadata from :meth:`~picamera2.Picamera2.capture_metadata`,
            used to read the current ``FrameDuration``.
        '''
        if 'FrameDurationLimits' not in self.device.camera_controls:
            return
        lo, hi, default = self.device.camera_controls['FrameDurationLimits']
        duration = metadata.get('FrameDuration', None)
        if duration is None:
            duration = default[0] if isinstance(default, tuple) else lo
        self._controlValues['FrameDurationLimits'] = (duration, duration)
        self.registerProperty(
            'fps',
            getter=self._getFps,
            setter=self._setFps,
            ptype=float,
            minimum=1_000_000 / hi,
            maximum=1_000_000 / lo,
        )

    def _getFps(self) -> float:
        duration = self._controlValues['FrameDurationLimits'][0]
        return 1_000_000 / duration

    def _setFps(self, fps: float) -> None:
        duration = int(1_000_000 / fps)
        self._setControl('FrameDurationLimits', (duration, duration))

    def _setControl(self, name: str, value) -> None:
        '''Apply a control value to the camera and update the local cache.'''
        self.device.set_controls({name: value})
        self._controlValues[name] = value

    def _getWidth(self) -> int:
        return self.device.camera_config['main']['size'][0]

    def _setWidth(self, value: int) -> None:
        self._reconfigure(width=int(value))
        self.shapeChanged.emit(self.shape)

    def _getHeight(self) -> int:
        return self.device.camera_config['main']['size'][1]

    def _setHeight(self, value: int) -> None:
        self._reconfigure(height=int(value))
        self.shapeChanged.emit(self.shape)

    def _reconfigure(self,
                     width: int | None = None,
                     height: int | None = None) -> None:
        '''Reconfigure the camera stream at a new resolution.

        Stops acquisition, applies the new resolution, restarts, and
        reapplies any controls that were set before reconfiguring.

        Parameters
        ----------
        width : int or None
            New frame width in pixels.  ``None`` keeps the current width.
        height : int or None
            New frame height in pixels.  ``None`` keeps the current height.
        '''
        w, h = self.device.camera_config['main']['size']
        if width is not None:
            w = int(width)
        if height is not None:
            h = int(height)
        self.device.stop()
        config = self.device.create_preview_configuration(
            main={'size': (w, h), 'format': 'RGB888'})
        self.device.configure(config)
        self.device.start()
        if self._controlValues:
            self.device.set_controls(self._controlValues)

    def _deinitialize(self) -> None:
        '''Stop acquisition and close the Raspberry Pi camera.'''
        self.device.stop()
        self.device.close()

    def read(self) -> QCamera.CameraData:
        '''Read one frame from the camera.

        Uses :meth:`~picamera2.Picamera2.capture_request` for direct buffer
        access, which avoids an extra copy compared to
        :meth:`~picamera2.Picamera2.capture_array`.

        Returns
        -------
        tuple[bool, ndarray or None]
            ``(True, frame)`` on success, ``(False, None)`` on failure.
        '''
        if not self.isOpen():
            return False, None
        try:
            request = self.device.capture_request()
            frame = request.make_array('main').copy()
            request.release()
        except Exception as ex:
            logger.warning(f'Frame read failed: {ex}')
            return False, None
        return True, frame


class QPicameraSource(QVideoSource):

    '''Threaded video source backed by :class:`QPicamera`.

    Parameters
    ----------
    camera : QPicamera or None
        Camera instance to wrap.  If ``None``, a new :class:`QPicamera`
        is created from the remaining arguments.
    *args :
        Forwarded to :class:`QPicamera` when *camera* is ``None``.
    **kwargs :
        Forwarded to :class:`QPicamera` when *camera* is ``None``.
    '''

    def __init__(self, *args,
                 camera: QPicamera | None = None,
                 **kwargs) -> None:
        camera = camera or QPicamera(*args, **kwargs)
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QPicamera.example()
