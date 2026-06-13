from typing import TYPE_CHECKING
from QVideo.lib import QCamera, QVideoSource
import logging

if TYPE_CHECKING:
    from picamera2 import Picamera2

try:
    from picamera2 import Picamera2
    from libcamera import Transform
except (ImportError, ModuleNotFoundError):
    Picamera2 = None
    Transform = None


logger = logging.getLogger(__name__)


__all__ = ['QPicamera', 'QPicameraSource']


# picamera2 control names and their Python types.
# Only controls listed here are probed and registered as properties.
_CONTROL_TYPES: dict[str, type] = {
    'AeEnable':     bool,
    'AwbEnable':    bool,
    'AwbMode':      int,
    'Brightness':   float,
    'Contrast':     float,
    'Saturation':   float,
    'Sharpness':    float,
    'ExposureTime': int,
    'AnalogueGain': float,
    'AfMode':       int,
    'AfRange':      int,
    'AfSpeed':      int,
    'LensPosition': float,
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
    gray : bool
        ``True`` convert frames to grayscale.
        Default: ``False``.
    hflip : bool
        ``True`` to mirror frames horizontally.  Default: ``False``.
    vflip : bool
        ``True`` to flip frames vertically.  Default: ``False``.
    *args :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    '''

    def __init__(self, *args,
                 cameraID: int = 0,
                 width: int = 1280,
                 height: int = 960,
                 gray: bool = False,
                 hflip: bool = False,
                 vflip: bool = False,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cameraID = cameraID
        self._width = int(width)
        self._height = int(height)
        self._gray = bool(gray)
        self._hflip = bool(hflip)
        self._vflip = bool(vflip)
        self._controlValues: dict[str, object] = {}
        # Tracks whether the picamera2 hardware is actively streaming.
        # Distinct from self._isOpen so that _setControl can cache values
        # between a stop/restart cycle (e.g. when fps changes while closed).
        self._deviceOpen: bool = False
        self._device: 'Picamera2 | None' = None
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
            self._device = Picamera2(camera_num=self._cameraID)
        except Exception as ex:
            logger.warning('Could not open Raspberry Pi camera'
                           f'{self._cameraID}: {ex}')
            return False
        try:
            info = self._device.global_camera_info()
            if isinstance(info, list) and self._cameraID < len(info):
                self._modelName = info[self._cameraID].get('Model')
        except Exception:
            pass
        # Save controls set before this restart (e.g. fps changed while
        # the device was closed).  _probeControls will overwrite
        # _controlValues from fresh metadata, so we save them here and
        # re-apply them afterwards.
        prior_controls = dict(self._controlValues)
        fmt = 'YUV420' if self._gray else 'BGR888'
        cfg_kwargs = {
            'main': {'size': (self._width, self._height), 'format': fmt}}
        t = self._makeTransform()
        if t is not None:
            cfg_kwargs['transform'] = t
        config = self._device.create_preview_configuration(**cfg_kwargs)
        self._device.configure(config)
        self._device.start()
        self._deviceOpen = True
        try:
            self._device.capture_array()
        except Exception as ex:
            logger.warning(f'Camera did not deliver a frame: {ex}')
            self._deviceOpen = False
            self._device.stop()
            self._device.close()
            return False
        register = self.registerProperty
        register('width', getter=self._getWidth,
                 setter=self._setWidth, ptype=int)
        register('height', getter=self._getHeight,
                 setter=self._setHeight, ptype=int)
        register('color', getter=self._getColor,
                 setter=self._setColor, ptype=bool)
        register('hflip', getter=self._getHflip,
                 setter=self._setHflip, ptype=bool)
        register('vflip', getter=self._getVflip,
                 setter=self._setVflip, ptype=bool)
        metadata = self._device.capture_metadata()
        self._probeControls(metadata)
        self._registerFrameRate(metadata)
        self._probeFocus(metadata)
        self._probeColourGains(metadata)
        # Re-apply any controls the user set before this restart.
        # Filter to keys still valid under the new configuration.
        pending = {k: v for k, v in prior_controls.items()
                   if k in self._controlValues}
        if pending:
            self._device.set_controls(pending)
            self._controlValues.update(pending)
        return True

    def _probeControls(self, metadata: dict[str, object]) -> None:
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
            if name not in self._device.camera_controls:
                continue
            lo, hi, default = self._device.camera_controls[name]
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

    def _registerFrameRate(self, metadata: dict[str, object]) -> None:
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
        if 'FrameDurationLimits' not in self._device.camera_controls:
            return
        lo, hi, default = self._device.camera_controls['FrameDurationLimits']
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

    def _probeFocus(self, metadata: dict[str, object]) -> None:
        '''Register autofocus controls if the camera supports AF.

        AF support is detected by the presence of ``AfTrigger`` in
        ``camera_controls``.  When supported, ``AfState`` is registered
        as a read-only property (updated per frame in :meth:`read`) and
        ``autofocus`` is registered as a trigger method.

        Parameters
        ----------
        metadata : dict
            Frame metadata from :meth:`~picamera2.Picamera2.capture_metadata`,
            used to initialise the cached ``AfState`` value.
        '''
        if 'AfTrigger' not in self._device.camera_controls:
            return
        self._controlValues['AfState'] = int(metadata.get('AfState', 0))
        self.registerProperty(
            'AfState',
            getter=lambda: int(self._controlValues.get('AfState', 0)),
            setter=None,
            ptype=int,
        )
        self.registerMethod('autofocus', self._triggerAutofocus)

    def _probeColourGains(self, metadata: dict[str, object]) -> None:
        '''Register ``ColourGainR`` and ``ColourGainB`` if supported.

        ``ColourGains`` is a ``(R_gain, B_gain)`` tuple in picamera2 and
        cannot be expressed as a single scalar property.  It is split into
        two independent float properties that share the same underlying
        ``ColourGains`` control so they can be adjusted separately from
        the control tree.

        Parameters
        ----------
        metadata : dict
            Frame metadata from :meth:`~picamera2.Picamera2.capture_metadata`,
            used to initialise cached gain values.
        '''
        if 'ColourGains' not in self._device.camera_controls:
            return
        lo, hi, _ = self._device.camera_controls['ColourGains']
        current = metadata.get('ColourGains', None)
        if not isinstance(current, (tuple, list)) or len(current) < 2:
            current = (1.0, 1.0)
        self._controlValues['ColourGains'] = (
            float(current[0]), float(current[1]))
        meta = {}
        if lo is not None:
            meta['minimum'] = lo
        if hi is not None:
            meta['maximum'] = hi
        self.registerProperty(
            'ColourGainR',
            getter=lambda: self._controlValues['ColourGains'][0],
            setter=self._setColourGainR,
            ptype=float,
            **meta)
        self.registerProperty(
            'ColourGainB',
            getter=lambda: self._controlValues['ColourGains'][1],
            setter=self._setColourGainB,
            ptype=float,
            **meta)

    def _setColourGainR(self, value: float) -> None:
        _, b = self._controlValues['ColourGains']
        self._setControl('ColourGains', (float(value), b))

    def _setColourGainB(self, value: float) -> None:
        r, _ = self._controlValues['ColourGains']
        self._setControl('ColourGains', (r, float(value)))

    def _triggerAutofocus(self) -> None:
        '''Send ``AfTrigger=Start`` to begin a single autofocus sweep.'''
        if self._deviceOpen:
            self._device.set_controls({'AfTrigger': 0})

    def _getFps(self) -> float:
        duration = self._controlValues['FrameDurationLimits'][0]
        return 1_000_000 / duration

    def _setFps(self, fps: float) -> None:
        duration = int(1_000_000 / fps)
        self._setControl('FrameDurationLimits', (duration, duration))

    def _setControl(self, name: str, value: object) -> None:
        '''Update the control cache and apply to the device if it is open.

        When called while the device is closed (e.g. fps changed between
        stop and restart), the value is stored so that :meth:`_initialize`
        can re-apply it once the device is reopened.
        '''
        self._controlValues[name] = value
        if self._deviceOpen:
            self._device.set_controls({name: value})

    def _getColor(self) -> bool:
        return not self._gray

    def _setColor(self, value: bool) -> None:
        self._gray = not bool(value)
        self._reconfigure()
        self.shapeChanged.emit(self.shape)

    def _getHflip(self) -> bool:
        return self._hflip

    def _setHflip(self, value: bool) -> None:
        self._hflip = bool(value)
        self._reconfigure()

    def _getVflip(self) -> bool:
        return self._vflip

    def _setVflip(self, value: bool) -> None:
        self._vflip = bool(value)
        self._reconfigure()

    def _makeTransform(self) -> 'Transform | None':
        if Transform is None:
            return None
        return Transform(hflip=self._hflip, vflip=self._vflip)

    def _getWidth(self) -> int:
        return self._device.camera_config['main']['size'][0]

    def _setWidth(self, value: int) -> None:
        '''Store the requested width so the next
        :meth:`_initialize` applies it.

        Resolution changes require stopping and restarting the picamera2
        stream, handled by
        :class:`~QVideo.lib.QVideoSource.QVideoSource`.
        Storing the value here lets :meth:`_initialize` apply it on
        restart via
        :meth:`~picamera2.Picamera2.create_preview_configuration`.
        '''
        self._width = int(value)

    def _getHeight(self) -> int:
        return self._device.camera_config['main']['size'][1]

    def _setHeight(self, value: int) -> None:
        '''Store the requested height so the next
        :meth:`_initialize` applies it.

        See :meth:`_setWidth` for rationale.
        '''
        self._height = int(value)

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
        w, h = self._device.camera_config['main']['size']
        if width is not None:
            w = int(width)
        if height is not None:
            h = int(height)
        self._device.stop()
        fmt = 'YUV420' if self._gray else 'BGR888'
        cfg_kwargs = {'main': {'size': (w, h), 'format': fmt}}
        t = self._makeTransform()
        if t is not None:
            cfg_kwargs['transform'] = t
        config = self._device.create_preview_configuration(**cfg_kwargs)
        self._device.configure(config)
        self._device.start()
        # Re-apply cached controls.  Note: _reconfigure does not rebuild
        # _properties, so if the new configuration changes available controls
        # or their ranges the stale registrations will persist silently.
        if self._controlValues:
            self._device.set_controls(self._controlValues)

    def _deinitialize(self) -> None:
        '''Stop acquisition and close the Raspberry Pi camera.'''
        self._deviceOpen = False
        self._device.stop()
        self._device.close()

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
            request = self._device.capture_request()
            frame = request.make_array('main').copy()
            if 'AfState' in self._controlValues:
                req_meta = request.get_metadata()
                if 'AfState' in req_meta:
                    self._controlValues['AfState'] = int(req_meta['AfState'])
            request.release()
        except Exception as ex:
            logger.warning(f'Frame read failed: {ex}')
            return False, None
        if self._gray:
            # Convert YUV420 to grayscale by taking the Y channel.
            frame = frame[:self.height, :self.width]
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
        camera = camera if camera is not None else QPicamera(*args, **kwargs)
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QPicamera.example()
