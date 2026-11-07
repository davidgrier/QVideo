'''GenICam cameras and sources, driven through viva-genicam.'''
from contextlib import suppress
from functools import partial
import logging
import re
from QVideo.lib import QCamera
from QVideo.lib.errors import QDeviceError
from typing import ClassVar

try:
    import viva_genicam as vg
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError(
        f"QVivaCamera could not import 'viva_genicam': {exc}\n"
        '\tInstall it with: pip install viva-genicam') from exc


logger = logging.getLogger(__name__)


__all__ = ['QVivaCamera']

#: The feature kinds that become properties: the Python type of each, and
#: the camera calls that read and write it.
_KINDS = {'Integer': (int, 'integer'),
          'IntConverter': (int, 'integer'),
          'Float': (float, 'float'),
          'Converter': (float, 'float'),
          'Boolean': (bool, 'bool'),
          'Enumeration': (str, 'enum'),
          'StringReg': (str, 'string')}


_DEEP_FORMAT = re.compile(r'(?:Mono|Bayer[A-Z]{2})(\d+)')


def _pixelLevels(pixelFormat: str | None) -> tuple[int, int] | None:
    '''Return the levels of the pixel format, ``None`` if it fills its type.

    A format of more than 8 and fewer than 16 bits (``Mono12``,
    ``Mono10p``, ``BayerRG12Packed``) is delivered as counts, right
    justified in ``uint16``: ``Mono12`` has levels ``(0, 4095)``.
    '''
    match = _DEEP_FORMAT.match(str(pixelFormat))
    bits = int(match[1]) if match else 8
    return (0, 2**bits - 1) if 8 < bits < 16 else None


class QVivaCamera(QCamera):

    '''GenICam camera on USB3 Vision or GigE Vision, via viva-genicam.

    `viva-genicam <https://github.com/VitalyVorobyev/viva-genicam>`_ is a
    GenICam stack written in Rust.  It speaks the camera's protocol
    itself, so it needs no GenTL producer and no vendor SDK, and it
    releases the interpreter lock while it waits for a frame, so the
    interface of a program stays responsive while the camera streams.

    The camera opens USB3 Vision devices first and GigE Vision devices
    after them; *cameraID* indexes that list.  Every feature of the
    camera's node map that can be read becomes a property, and every
    command a method.

    Requires the ``viva-genicam`` package (``pip install viva-genicam``).

    Parameters
    ----------
    cameraID : int
        Index of the camera to open.  Default: ``0``.
    *args :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    '''

    #: How long :meth:`read` waits for a frame [ms].
    timeout = 1000

    #: SFNC nodes behind the lowercase names that every camera shares, in
    #: order of preference.
    _ALIAS_NODES: ClassVar[dict[str, tuple[str, ...]]] = {'width': ('Width',),
                    'height': ('Height',),
                    'fps': ('AcquisitionFrameRate',
                            'AcquisitionFrameRateAbs')}

    #: Nodes that report the frame rate that the camera delivers, in order
    #: of preference.
    _ACTUAL_FPS_NODES = ('AcquisitionResultingFrameRate',
                         'ResultingFrameRateAbs',
                         'ResultingFrameRate')

    def __init__(self, *args, cameraID: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cameraID = cameraID
        self._device: vg.Camera | None = None
        self._stream: vg.FrameStream | None = None
        self._kinds: dict[str, str] = {}
        self._streamLocked: set[str] = set()
        #: Why the last read failed; the reason when the stream then ends.
        self._readError: str | None = None
        self.open()

    def _initialize(self) -> bool:
        '''Open the device, register its features and start streaming.'''
        try:
            self._device = self._connect()
            self._registerFeatures()
            self._registerAliases()
            self._updateLevels()
            with suppress(Exception):
                self._modelName = self._device.get_string('DeviceModelName')
            try:  # maps frame times to the host clock
                self._device.time_calibrate()
            except Exception as ex:
                # Only GigE Vision cameras can be calibrated, so a USB3
                # Vision camera always lands here, and its frames have no
                # host timestamp: that is no failure to warn of.
                level = (logging.WARNING if self._device.transport == 'gige'
                         else logging.DEBUG)
                logger.log(level, f'Could not calibrate the camera clock: '
                           f'{ex}; the timestamps of the frames are those '
                           'of the clock of the camera')
            self._startStream()
            self._findStreamLocked()
        except Exception:
            self._cleanup()  # a camera that is half open stays claimed
            raise
        return True

    def set(self, key: str, value: QCamera.PropertyValue) -> None:
        '''Set a property; a new pixel format changes the levels.'''
        super().set(key, value)
        if self._canonical(key) == 'PixelFormat':
            self._updateLevels()

    def _updateLevels(self) -> None:
        '''Read the pixel format and keep the levels that it implies.

        The source copies :attr:`levels` into every frame, so the format is
        read when it can have changed and not for each frame.
        '''
        if 'PixelFormat' in self.properties:
            self.levels = _pixelLevels(self.get('PixelFormat'))

    def _connect(self) -> 'vg.Camera':
        '''Return the camera that *cameraID* names.

        USB3 Vision devices come first; GigE Vision devices are looked
        for (a broadcast on the network) only if *cameraID* is past them.
        '''
        devices = vg.discover_u3v()
        if self._cameraID >= len(devices):
            devices += vg.discover()
        if self._cameraID >= len(devices):
            raise QDeviceError(
                f'{type(self).__name__}: no camera {self._cameraID} '
                f'({len(devices)} found by viva-genicam).')
        info = devices[self._cameraID]
        if info.transport == 'u3v':
            self._checkLink(info)
            return vg.connect_u3v(info)
        return vg.connect_gige(info)

    def _checkLink(self, info: 'vg.U3vDeviceInfo') -> None:
        '''Warn if a USB3 Vision camera runs slower than SuperSpeed.

        A camera on a cable or port that lacks the SuperSpeed wires still
        enumerates and answers every command, but its stream is too slow
        or stalls: the first frame may never arrive.
        '''
        speed = info.speed
        if speed and not speed.lower().startswith('super'):
            logger.warning(
                f'{info.model}: the USB link runs at {speed}, not '
                'SuperSpeed.  Use a USB 3 cable and plug the camera into '
                'a USB 3 port, without a hub if possible.')

    # ------------------------------------------------------------------
    # Features
    # ------------------------------------------------------------------

    def _registerFeatures(self) -> None:
        '''Register the readable features as properties and the commands
        as methods.'''
        for info in self._device.all_node_info():
            if info.kind == 'Command':
                self.registerMethod(
                    info.name, partial(self._device.execute, info.name))
            elif info.kind in _KINDS:
                self._registerFeature(info.name, info.kind)

    def _registerFeature(self, name: str, kind: str) -> None:
        ptype, call = _KINDS[kind]
        try:
            state = self._device.feature_state(name)
        except vg.GenicamError as ex:
            logger.debug(f'{name} skipped: {ex}')
            return
        if state.access not in ('RO', 'RW') or not state.is_available:
            return
        self._kinds[name] = kind
        meta = {}
        if state.range is not None:
            meta.update(minimum=ptype(state.range.min),
                        maximum=ptype(state.range.max))
            if state.range.inc:
                meta['step'] = ptype(state.range.inc)
        if state.enum_entries:
            meta['limits'] = list(state.enum_entries)
        setter = (self._setter(name, call, ptype)
                  if self._isWritable(state, name) else None)
        self.registerProperty(name, getter=self._getter(name, call),
                              setter=setter, ptype=ptype, **meta)

    def _isWritable(self, state: 'vg.FeatureState', name: str) -> bool:
        '''Whether a feature with *state* accepts a value now.

        A feature that the stream locks reads as read-only while it runs,
        but it is written with the stream stopped.
        '''
        return state.access == 'RW' or name in self._streamLocked

    def _findStreamLocked(self) -> None:
        '''Find the features that the stream locks: those that were
        writable before it started and are not now.'''
        self._streamLocked = {
            name for name, spec in self.properties.items()
            if spec['setter'] is not None
            and self._device.feature_state(name).access != 'RW'}

    def updateAccess(self) -> None:
        '''Give a setter to the features that are writable now, and take
        it from those that are not.

        A camera changes what can be written as its settings change: the
        exposure time is read-only while the exposure is automatic.  Call
        this after a change, and each property is writable exactly when
        it has a setter.
        '''
        if not self.isOpen():
            return
        for name, kind in self._kinds.items():
            state = self._device.feature_state(name)
            writable = self._isWritable(state, name)
            if writable != (self.properties[name]['setter'] is not None):
                self._registerFeature(name, kind)

    def _getter(self, name: str, call: str):
        '''Return a reader of feature *name*, ``None`` when it is not
        readable now.'''
        read = getattr(self._device, f'get_{call}')

        def getter():
            try:
                return read(name)
            except vg.GenicamError:
                return None
        return getter

    def _setter(self, name: str, call: str, ptype: type):
        '''Return a writer of feature *name*.

        Only features that were writable when the camera opened get one.
        Of those, a feature that the camera locks while it streams (the
        frame size, the pixel format) is written with the stream
        stopped.  A write that fails is reported and not raised.
        '''
        write = getattr(self._device, f'set_{call}')

        def setter(value):
            value = ptype(value)
            try:
                write(name, value)
            except vg.GenicamError as ex:
                logger.debug(f'{name} not written while streaming: {ex}')
                self._writeStopped(write, name, value)
        return setter

    def _writeStopped(self, write, name: str, value) -> None:
        '''Write with the stream stopped, then start it again.'''
        self._stopStream()
        try:
            write(name, value)
        except vg.GenicamError as ex:
            logger.warning(f'{name} is not currently writable: {ex}')
        finally:
            try:
                self._startStream()
            except vg.TransportError as ex:
                self._deviceLost(str(ex))

    def _registerAliases(self) -> None:
        '''Offer the lowercase names for the standard nodes that exist.'''
        for alias, nodes in self._ALIAS_NODES.items():
            for node in nodes:
                if node in self.properties and alias not in self.properties:
                    self.aliases[alias] = node
                    break

    @property
    def actualFps(self) -> float:
        '''Frame rate that the camera reports it delivers.

        The first of :attr:`_ACTUAL_FPS_NODES` that the camera has and
        that reads as a positive number; otherwise ``fps``, the rate that
        was asked for.
        '''
        for name in self._ACTUAL_FPS_NODES:
            if name in self.properties:
                value = self.properties[name]['getter']()
                if value and value > 0.:
                    return float(value)
        return self.fps

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def _startStream(self) -> None:
        '''Open a stream; this starts the acquisition.'''
        self._stream = self._device.stream()
        self._stream.__enter__()

    def _stopStream(self) -> None:
        '''Stop the acquisition and close the stream.'''
        stream, self._stream = self._stream, None
        if stream is not None:
            with suppress(Exception):
                stream.__exit__(None, None, None)

    def _cleanup(self) -> None:
        '''Release what is open; safe however far initialization got.'''
        self._stopStream()
        device, self._device = self._device, None
        if device is not None:
            with suppress(Exception):
                device.close()

    def _deinitialize(self) -> None:
        '''Stop the acquisition and release the device.'''
        self._cleanup()

    def read(self) -> QCamera.CameraData:
        '''Read one frame from the camera.

        Waits for the frame with the interpreter lock released.

        Returns
        -------
        tuple[bool, ndarray or None]
            ``(True, frame)`` on success, ``(False, None)`` on timeout.
        '''
        self.hardwareTimestamp = None
        try:
            frame = self._stream.next_frame(timeout_ms=self.timeout)
            if frame is None:
                # A stream that is alive raises when it has no frame (a
                # timeout is an error too) and never returns None: it ends
                # when the device goes, after the error that said why.
                self._deviceLost(
                    'the camera stopped sending frames'
                    + (f' ({self._readError})' if self._readError else ''))
                return False, None
            image = frame.to_numpy()
        except vg.GenicamError as ex:
            self._readError = str(ex)
            logger.warning(f'camera read failed: {ex}')
            return False, None
        self._readError = None
        self.hardwareTimestamp = self._timestamp(frame)
        return True, image

    @staticmethod
    def _timestamp(frame) -> float | None:
        '''Return the time that the camera gave *frame* [s], or ``None``.

        viva-genicam maps the timestamp of the camera to host time (POSIX
        seconds) for a camera that it can calibrate, GigE Vision.  A USB3
        Vision camera cannot be calibrated, so its frames have only the
        ticks of the camera, which are nanoseconds (a Blackfly S counted
        999.8 million of them a second against the clock of the host).  The
        seconds of that clock are good for the time between frames, not for
        the time of day.  Replace this when viva-genicam gives the time.
        '''
        if frame.ts_host is not None:
            return frame.ts_host
        if frame.ts_dev:
            return frame.ts_dev * 1e-9
        return None

