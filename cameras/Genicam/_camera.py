'''GenICam cameras and sources, driven through Harvesters.

:class:`QGenicamCamera` is the base of every GenICam backend that needs a
GenTL producer (a vendor's ``.cti`` file); the backends of Basler, Flir,
IDS, MATRIX VISION and Allied Vision only say which producer to load.

For a GenICam camera, :class:`~QVideo.cameras.Viva.QVivaCamera` is the
preferred interface.  This one needs a ``.cti`` file and its binding holds
the interpreter lock, so the chooser opens it in a process of its own
(:class:`~QVideo.lib.remote.camera.QRemoteCamera`) on macOS and Linux;
creating the class yourself keeps it in the program.

The camera has four parts, in this order.

1. **Opening and closing**: load the producer, open the device, start the
   acquisition and find the features that acquisition makes read-only.
2. **Reading frames**: one frame per :meth:`~QGenicamCamera.read`.
3. **Properties**: every readable node becomes a registered property with
   the type and limits of the node, and every command becomes a method.
4. **The node map**: the nodes themselves, as plain data
   (:meth:`~QGenicamCamera.nodeTree`) for a tree to build from and as
   snapshots (:meth:`~QGenicamCamera.states`) for a tree to refresh from.
5. **Changes on its own**: a camera that adjusts the exposure or the gain
   is asked what changed, only when something can have
   (:meth:`~QGenicamCamera._changes`), and the tree follows
   (``propertiesChanged``).

**The camera lock.**  Every access to the node map holds ``camera._mutex``.
The ``genicam`` binding keeps the interpreter lock while it waits for the
lock of the node map, so a thread that touches the map without the camera
lock can deadlock with a thread that holds the map and calls back into
Python.  A new method that reads or writes a node must take the lock.

**The types of nodes.**  The module ``_nodes`` is the one place that
knows them (enumeration, boolean, integer, float, string, register, and the
groups and commands that hold no value): what a node is, what bounds it,
how to read and write it, and how to describe it as plain data.  The camera
decides when, and holds the lock.
'''
import logging
import os
import re
import time
from collections.abc import Callable, Iterable
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar


from QVideo.lib import QCamera
from QVideo.lib.errors import QDeviceError, QDriverError
from QVideo.cameras import gentl

if TYPE_CHECKING:
    from harvesters.core import ImageAcquirer
    from genicam.genapi import NodeMap

try:
    from harvesters.core import Harvester
    from genicam.genapi import IValue, EAccessMode
    from genicam.gentl import TimeoutException
except ImportError as exc:
    raise ImportError(
        f"QGenicamCamera could not import 'genicam': {exc}\n"
        '\tInstall it with: pip install genicam harvesters\n'
        '\tIf the error persists, try downgrading to numpy 1.x:\n'
        '\t  pip install "numpy<2"'
    ) from exc


from QVideo.cameras.Genicam import _nodes  # noqa: E402

logger = logging.getLogger(__name__)


__all__ = ['QGenicamCamera']

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


class QGenicamCamera(QCamera):

    '''Abstract base for GenICam-compliant cameras accessed via Harvesters.

    `GenICam <https://www.emva.org/standards-technology/genicam/>`_ is a
    standardized machine-vision interface maintained by the European Machine
    Vision Association.  Communication with the physical device is handled by
    a GenTL producer — a ``.cti`` binary supplied by the camera manufacturer.

    Subclasses **must** set the :attr:`producer` class attribute to the path
    of the appropriate ``.cti`` file before instantiating.  Attempting to
    instantiate :class:`QGenicamCamera` directly raises
    :exc:`~QVideo.lib.errors.QDriverError`.

    Every access to the node map holds the camera lock, which
    serializes it with the reads of frames (see the module docstring).

    Requires the ``genicam`` and ``harvesters`` packages
    (``pip install genicam harvesters``).

    Attributes
    ----------
    producer : str or None
        Path to the GenTL producer ``.cti`` file.  Must be overridden by
        concrete subclasses.

    Parameters
    ----------
    cameraID : int
        Index of the camera to open.  Default: ``0``.
    *args :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    '''

    producer: str | Path | None = None
    #: File names of the producer to look for on the GenTL path, in
    #: order of preference; a subclass that sets no ``producer`` sets this.
    _producerFilenames: tuple[str, ...] = ()
    #: Text added to the error when the producer is not found: where to
    #: get it, or how to point the GenTL path at it.
    _producerHint: str = ''
    #: SFNC nodes behind the lowercase names that every camera shares, in
    #: order of preference.
    _ALIAS_NODES: ClassVar[dict[str, tuple[str, ...]]] = {'width': ('Width',),
                    'height': ('Height',),
                    'fps': ('AcquisitionFrameRate',
                            'AcquisitionFrameRateAbs')}

    #: Nodes that report the frame rate that the camera delivers, in order
    #: of preference: the standard name, then names of older firmware.
    _ACTUAL_FPS_NODES = ('AcquisitionResultingFrameRate',
                         'ResultingFrameRateAbs',
                         'ResultingFrameRate')

    def __init__(self, *args, cameraID: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cameraID = cameraID
        self._harvester: Harvester | None = None
        self._device: ImageAcquirer | None = None
        self._nodeMap: NodeMap | None = None
        self._protected: set[str] = set()
        self._armed = False
        self._quiet = 0
        self._nextPoll = 0.
        self._lastPoll = 0.
        self._autos: set[str] = set()
        self._reported: dict[str, QCamera.PropertyValue] = {}
        self.open()

    # ------------------------------------------------------------------
    # Opening and closing the device
    # ------------------------------------------------------------------

    def _initialize(self) -> bool:
        '''Open the GenICam device and register available properties.

        Returns
        -------
        bool
            ``True`` if a valid camera device was opened successfully.
        '''
        try:
            self._openDevice(self._locateProducer())
            self._connectNodeMap()
            root = self.node()
            self._protected = self._startAcquisition(root)
            self._registerFeatures(root)
            with suppress(Exception):
                self._modelName = str(self._nodeMap.DeviceModelName.value)
            self._registerAliases()
            self._updateLevels()
            self._checkLink()
        except Exception:
            self._cleanup()  # a camera that is half open stays claimed
            raise
        return True

    def set(self, key: str, value: QCamera.PropertyValue) -> None:
        '''Set a property; a new pixel format changes the levels.

        A write while properties are watched starts asking the camera what
        changed (see :meth:`_changes`): the binding does not say which nodes
        a write invalidates.
        '''
        super().set(key, value)
        if self._watched:
            self._arm()
        if self._canonical(key) == 'PixelFormat':
            self._updateLevels()

    def _updateLevels(self) -> None:
        '''Read the pixel format and keep the levels that it implies.

        The source copies :attr:`levels` into every frame, so the format is
        read when it can have changed and not for each frame.
        '''
        if 'PixelFormat' in self.properties:
            self.levels = _pixelLevels(self.get('PixelFormat'))

    def _openDevice(self, producer: str) -> None:
        '''Load the GenTL *producer* and open the camera that it finds.'''
        self._harvester = Harvester()
        self._device = None
        try:
            self._harvester.add_file(producer)
            self._harvester.update()
        except Exception as ex:
            raise QDriverError(
                f'{type(self).__name__}: cannot load GenTL producer '
                f'{producer}: {ex}') from ex
        try:
            self._device = self._harvester.create(self._cameraID)
        except Exception as ex:
            count = len(self._harvester.device_info_list)
            raise QDeviceError(
                f'{type(self).__name__}: cannot open camera '
                f'{self._cameraID} ({count} found via {Path(producer).name}'
                f'): {ex}\n'
                'Check that the camera is connected and powered, and that '
                'you have permission to access it.') from ex

    def _connectNodeMap(self) -> None:
        '''Take the node map from the device, loading it by hand if
        harvesters did not connect it.'''
        self._nodeMap = self._device.remote_device.node_map
        if self._isConnected(self._nodeMap):
            return
        logger.debug('harvesters node map unconnected; '
                     'loading manually from device port')
        self._nodeMap = self._loadNodeMap(self._device)
        if self._nodeMap is None:
            raise QDeviceError(
                f'{type(self).__name__}: cannot read the GenICam '
                'node map from the camera')

    @staticmethod
    def _loadNodeMap(device: 'ImageAcquirer') -> 'NodeMap | None':
        '''Reload the node map by re-running harvesters' own loading logic.

        Called when harvesters' automatic node map loading fails due to a
        timing race: if the Spinnaker GenTL producer's port URL list is not
        yet populated at ``h.create()`` time, harvesters silently returns an
        unconnected ``NodeMap``.  Calling ``_create_node_map`` again once the
        port has settled produces a connected map, which is then patched back
        onto the device so that ``device.start()`` also uses it.

        .. warning::
            Accesses ``device.remote_device._create_node_map``, a private
            harvesters API.  Validated against harvesters 1.x; may break
            if harvesters internals change.

        Parameters
        ----------
        device : ImageAcquirer
            The device whose remote port will be queried.

        Returns
        -------
        NodeMap or None
            A connected node map, or ``None`` if loading failed.
        '''
        try:
            port = device.remote_device.module.remote_port
            nm = device.remote_device._create_node_map(port=port)
            device.remote_device._node_map = nm
            return nm
        except Exception as exc:
            logger.warning(f'manual node map load failed: {exc}')
            return None

    @staticmethod
    def _isConnected(nodeMap: 'NodeMap') -> bool:
        '''Return whether harvesters connected *nodeMap* to the camera.

        A node map that is not connected has no ``Root``.  Older versions of
        ``genicam`` answer ``False`` for it, and version 1.6 raises
        ``AccessException`` ("reference not valid") instead; both mean that
        the map must be loaded by hand.
        '''
        try:
            return nodeMap.has_node('Root')
        except Exception:
            return False

    @classmethod
    def _locateProducer(cls) -> str:
        '''Return the path to the GenTL producer, or explain why not.

        Raises
        ------
        QDriverError
            If no producer is configured, ``GENICAM_GENTL64_PATH`` is
            unset, or the producer file is not on that path.
        '''
        if cls.producer:
            return str(cls.producer)
        name = cls.__name__
        if not cls._producerFilenames:
            raise QDriverError(f'{name}: no GenTL producer configured')
        wanted = ' or '.join(cls._producerFilenames)
        hint = f'\n{cls._producerHint}' if cls._producerHint else ''
        if not gentl.gentlPaths():
            raise QDriverError(
                f'{name}: {gentl.ENV} is not set, so {wanted} cannot be '
                f'located.{hint}')
        found = cls._findProducer(*cls._producerFilenames)
        if found is None:
            searched = os.pathsep.join(gentl.gentlPaths())
            raise QDriverError(
                f'{name}: {wanted} not found in {gentl.ENV} '
                f'({searched}).{hint}')
        return found

    @staticmethod
    def _findProducer(*filenames: str) -> 'str | None':
        '''Search GENICAM_GENTL64_PATH for a matching GenTL producer.

        See :func:`QVideo.cameras.gentl.findProducer`.

        Parameters
        ----------
        *filenames : str
            Producer ``.cti`` filenames to search for, in priority order.

        Returns
        -------
        str or None
            Absolute path to the first ``.cti`` file found, or ``None`` if
            none of the requested producers exist on the path.
        '''
        return gentl.findProducer(*filenames)

    def _startAcquisition(self, root: IValue) -> 'set[str]':
        '''Start acquisition and return the features that it makes read-only.

        These are the features whose access mode differs before and after
        the start, so that writing them requires stopping acquisition.
        '''
        before = self._scanModes(root)
        self._device.start()
        self._keepNewestFrames()
        after = self._scanModes(root)
        return {name for name, mode in before.items()
                if name in after and after[name] != mode}

    @staticmethod
    def _scanModes(feature: IValue) -> dict[str, object]:
        '''Return a dict mapping property node names to their access modes.'''
        modes = {}
        kind = _nodes.nodeKind(feature)
        if kind == 'group':
            for f in feature.features:
                modes.update(QGenicamCamera._scanModes(f))
        elif kind in _nodes.PTYPES and kind != 'register':
            modes[feature.node.name] = feature.node.get_access_mode()
        return modes

    def _keepNewestFrames(self) -> None:
        '''Ask the producer to deliver the newest frame, not the oldest.

        By default a producer hands out the frames in the order in which
        they were captured, so a reader that is a little slower than the
        camera keeps a queue of old frames and shows video that lags.  A
        live view wants the frame that the camera captured last.  A
        producer that cannot do this keeps its default.
        '''
        with suppress(Exception):
            stream = self._device.data_streams[0].node_map
            stream.StreamBufferHandlingMode.value = 'NewestOnly'

    def _checkLink(self) -> None:
        '''Warn if a USB3 Vision camera runs slower than SuperSpeed.

        A camera on a cable or port that lacks the SuperSpeed wires still
        enumerates and answers every command, but its stream is too slow
        or stalls: the first frame may never arrive.
        '''
        if 'U3VCurrentSpeed' not in self.properties:
            return
        speed = self.get('U3VCurrentSpeed')
        if not str(speed).startswith('SuperSpeed'):
            logger.warning(
                f'{self.name}: the USB link runs at {speed}, not '
                'SuperSpeed.  Use a USB 3 cable and plug the camera into '
                'a USB 3 port, without a hub if possible.')

    def _registerAliases(self) -> None:
        '''Offer the lowercase names for the standard nodes that exist.'''
        for alias, nodes in self._ALIAS_NODES.items():
            for node in nodes:
                if node in self.properties and alias not in self.properties:
                    self.aliases[alias] = node
                    break

    @classmethod
    def precheck(cls) -> None:
        '''Raise now if the camera cannot open for want of a producer.

        The chooser calls this before it starts a worker process for the
        camera, so that a machine without the producer fails in a
        millisecond, in this process, with the message that opening the
        camera would give, and not after the start of a process.

        Raises
        ------
        QDriverError
            If no producer is configured, ``GENICAM_GENTL64_PATH`` is
            unset, or the producer file is not on that path.
        '''
        cls._locateProducer()

    def _cleanup(self) -> None:
        '''Release partially initialized resources after a failed _initialize.

        Safe to call regardless of how far initialization progressed.
        Each step is guarded so that a failure here does not mask the
        original exception.
        '''
        if self._device is not None:
            with suppress(Exception):
                self._device.stop()
            with suppress(Exception):
                self._device.destroy()
            self._device = None
        if self._harvester is not None:
            with suppress(Exception):
                self._harvester.reset()
        self._nodeMap = None

    def _deinitialize(self) -> None:
        '''Stop acquisition and release the GenICam device.'''
        self._cleanup()

    # ------------------------------------------------------------------
    # Reading frames
    # ------------------------------------------------------------------

    def read(self) -> QCamera.CameraData:
        '''Read one frame from the camera.

        Returns
        -------
        tuple[bool, ndarray or None]
            ``(True, frame)`` on success, ``(False, None)`` on timeout.
        '''
        frame = None
        self.hardwareTimestamp = None
        try:
            with self._device.fetch(timeout=1) as buffer:
                components = buffer.payload.components
                if not components:
                    logger.warning('camera returned empty payload')
                    return False, None
                image = components[0]
                height = image.height
                width = image.width
                channels = int(image.num_components_per_pixel)
                frame = image.data.copy()
                nanoseconds = buffer.timestamp_ns
                if nanoseconds:
                    self.hardwareTimestamp = nanoseconds * 1e-9
            frame = frame.reshape(height, width, channels).squeeze()
        except TimeoutException:
            logger.warning('camera acquisition timed out')
        except Exception as e:
            logger.warning(f'camera read failed: {e}')
        return frame is not None, frame

    @property
    def actualFps(self) -> float:
        '''Frame rate that the camera reports it delivers.

        The first of :attr:`_ACTUAL_FPS_NODES` that the camera has and
        that reads as a positive number; otherwise ``fps``, the rate that
        was asked for.
        '''
        for name in self._ACTUAL_FPS_NODES:
            if name in self.properties:
                try:
                    value = float(self.properties[name].getter())
                except Exception as ex:
                    logger.debug(f'cannot read {name}: {ex}')
                    continue
                if value > 0.:
                    return value
        return self.fps

    # ------------------------------------------------------------------
    # Properties: what the camera offers and how to read and write it
    # ------------------------------------------------------------------

    def _registerFeatures(self, feature: IValue) -> None:
        '''Recurse the node tree to register properties and methods.'''
        kind = _nodes.nodeKind(feature)
        if kind == 'group':
            for f in feature.features:
                self._registerFeatures(f)
        elif kind == 'action':
            self.registerMethod(feature.node.name, feature.execute)
        elif kind in _nodes.PTYPES:
            mode = feature.node.get_access_mode()
            if mode not in (EAccessMode.RO, EAccessMode.RW):
                return
            name = feature.node.name
            ptype, meta = _nodes.spec(feature, kind)
            setter = (None if kind == 'register'
                      else self._makeSetter(feature, name))
            self.registerProperty(name,
                                  getter=self._makeGetter(feature, kind),
                                  setter=setter,
                                  ptype=ptype,
                                  **meta)

    @staticmethod
    def _makeGetter(feature: IValue, kind: str) -> Callable[[], object]:
        '''Return a zero-argument callable that reads the feature value.

        The returned callable checks the current access mode before reading,
        returning ``None`` for features that are not readable at call time
        (e.g. enumeration nodes whose access mode changes after acquisition
        starts).
        '''
        def getter():
            mode = feature.node.get_access_mode()
            if mode not in (EAccessMode.RO, EAccessMode.RW):
                return None
            return _nodes.read(feature, kind)
        return getter

    def _makeSetter(self,
                     feature: IValue,
                     name: str) -> Callable[[QCamera.PropertyValue], None]:
        '''Return a setter that checks current access mode before writing.

        If the feature is not currently writable (and is not a protected
        feature that can be written after stopping acquisition), the write
        is skipped and a warning is logged.  Protected features stop and
        restart acquisition around the write as before.
        '''
        def setter(value):
            mode = feature.node.get_access_mode()
            if mode != EAccessMode.RW and name not in self._protected:
                logger.warning(
                    f'{name} is not currently writable (mode={mode})')
                return
            restart = name in self._protected and self._device.is_acquiring()
            if restart:
                self._device.stop()
            _nodes.write(feature, value)
            if restart:
                self._device.start()
        return setter

    # ------------------------------------------------------------------
    # The node map
    # ------------------------------------------------------------------

    def hasNode(self, name: str) -> bool:
        '''Return ``True`` if the named node exists in the node map.

        Like every access to the node map, this holds the camera lock: the
        ``genicam`` binding keeps the interpreter lock while it waits for
        the lock of the node map, so a thread that reads the map while
        another writes it can deadlock with it.

        Unlike :meth:`node`, this never logs a warning for missing names.
        Use it to guard calls to :meth:`node` in
        reactive code paths (e.g. UI update loops) where absent names are
        expected and not an error.

        Parameters
        ----------
        name : str
            GenICam node name to look up.

        Returns
        -------
        bool
            ``True`` if the node map is available and contains *name*.
        '''
        with self._mutex:
            return (self._nodeMap is not None
                    and self._nodeMap.has_node(name))

    def node(self, name: str = 'Root') -> 'IValue | None':
        '''Return the GenICam node with the given name.

        Parameters
        ----------
        name : str
            Node name to look up.  Default: ``'Root'``.

        Returns
        -------
        IValue or None
            The requested node, or ``None`` if it does not exist.
        '''
        with self._mutex:
            if self._nodeMap is None:
                return None
            if self._nodeMap.has_node(name):
                return self._nodeMap.get_node(name)
        logger.warning(f'node {name} is unknown')
        return None

    def nodeTree(self) -> dict:
        '''Return the node map as plain data, for a tree to build from.

        Only plain values (numbers, strings, lists, dicts) are returned,
        so the result crosses the process boundary of a
        :class:`~QVideo.lib.remote.camera.QRemoteCamera`.  Every entry has
        ``name``, ``title`` and ``visibility`` (an integer);
        a category adds ``type='group'`` and ``children``; a leaf adds
        ``type``, ``value``, ``default`` and the limits of its type.  A
        float adds ``unit`` and, if the node has an increment, ``step``.

        Returns
        -------
        dict
            The ``Root`` node, or an empty dict if there is no node map.
        '''
        root = self.node('Root')
        if root is None:
            return {}
        with self._mutex:
            return _nodes.describe(root)

    # ------------------------------------------------------------------
    # Snapshots of the nodes, for a tree to refresh from
    # ------------------------------------------------------------------

    def state(self, name: str) -> dict[str, object]:
        '''Return a snapshot of the named node, read under the device lock.

        See :meth:`states`.

        Parameters
        ----------
        name : str
            GenICam node name.  It must exist (see :meth:`hasNode`).

        Returns
        -------
        dict
            ``access`` (:class:`EAccessMode`), ``writable`` (``True`` if
            the node can be written now, or after stopping acquisition)
            and ``kind`` (``'int'``, ``'float'``, ``'enum'``,
            ``'register'`` or ``'other'``) always; ``min``, ``max`` and
            ``inc`` for numbers (``inc`` is ``None`` when the node has no
            increment); ``entries`` (symbolic names) for an enumeration;
            ``length`` and ``address`` for a register; and ``value`` when
            the node is readable.
        '''
        return self.states([name])[name]

    #: Seconds between asking the camera what changed.  The XML of a camera
    #: declares a ``PollingTime`` for the nodes that change by themselves
    #: (0.5 s for the exposure and its mode on a Blackfly S), and a read
    #: gives the value of the camera only after :meth:`NodeMap.poll` has
    #: been told that the time has passed.
    POLL_PERIOD = 0.5

    #: Polls without news after which the camera stops asking, unless a
    #: node is in an automatic mode.
    QUIET = 2

    #: Parts of the names of nodes that change all the time (counters,
    #: temperatures, the time since power-up).  They are reported, but they
    #: are no reason to keep asking.
    FREE_RUNNING = ('Uptime', 'Temperature', 'Voltage', 'Current',
                    'Throughput', 'Timestamp', 'Counter', 'Queue',
                    'Status', 'Count')

    def watch(self, names: Iterable[str]) -> None:
        '''Name the nodes to report, and look at them once.

        The automatic modes among them (SFNC names them ``...Auto``, with
        ``Off`` for manual) keep the camera asking while they are not off.
        '''
        super().watch(names)
        self._autos = {name for name in self._watched
                       if name.endswith('Auto')}
        self._reported = QCamera.snapshot(self, self._watched)
        self._arm()

    def _arm(self) -> None:
        '''Start asking the camera what changed.'''
        self._armed = True
        self._quiet = 0
        self._nextPoll = 0.

    def _changes(self) -> QCamera.Settings | None:
        '''Return the watched nodes that the camera changed on its own.

        The camera is not asked until something can change: a write while
        nodes are watched arms it, and an automatic mode that is not off
        keeps it armed.  Then the node map is told how long it has been
        (``NodeMap.poll``, which refreshes the nodes whose polling time has
        passed) and the watched nodes are read, in the hold of the camera
        that the frame was read in.  A value that differs from the last one
        is returned.  After :attr:`QUIET` polls without news from the nodes
        that do not :attr:`FREE_RUNNING`, and with no automatic mode on,
        the camera is left alone again.
        '''
        now = time.monotonic()
        if not self._armed or now < self._nextPoll:
            return None
        elapsed = max(1, round((now - (self._lastPoll or now)) * 1000))
        self._lastPoll = now
        self._nextPoll = now + self.POLL_PERIOD
        try:
            self._nodeMap.poll(elapsed)
        except Exception as ex:
            logger.debug(f'poll failed: {ex}')
            return None
        values = QCamera.snapshot(self, self._watched)
        changed = {name: value for name, value in values.items()
                   if self._reported.get(name) != value}
        self._reported.update(values)
        news = any(not any(part in name for part in self.FREE_RUNNING)
                   for name in changed)
        self._quiet = 0 if news else self._quiet + 1
        automatic = any(values.get(name, 'Off') != 'Off'
                        for name in self._autos)
        if self._quiet >= self.QUIET and not automatic:
            self._armed = False
            self._lastPoll = 0.
        return changed or None

    def states(self, names: Iterable[str]) -> dict[str, dict[str, object]]:
        '''Return snapshots of the named nodes, read under one lock.

        Read the device through this method, not through :meth:`node`,
        wherever acquisition may be running (for example a GUI that polls
        the hardware): it never overlaps a frame read.  The camera thread
        holds the lock while it waits for a frame, so a reader that has to
        queue for it once for every node is slow; ask for the nodes that
        you need together.

        Parameters
        ----------
        names : iterable of str
            GenICam node names.  Each must exist (see :meth:`hasNode`).
        Returns
        -------
        dict
            The result of :meth:`state` for each name.
        '''
        with self._mutex:
            nodes = {name: self.node(name) for name in names}
            return {name: _nodes.snapshot(node, name in self._protected)
                    for name, node in nodes.items()}



if __name__ == '__main__':  # pragma: no cover
    QGenicamCamera.example()
