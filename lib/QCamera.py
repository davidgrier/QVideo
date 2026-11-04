'''Abstract base class for all QVideo camera backends.'''
import logging
import threading
from abc import abstractmethod
from collections.abc import Callable
from functools import wraps
from types import TracebackType

from qtpy import QtCore

from QVideo.lib._qabc import QABCMeta
from QVideo.lib.videotypes import Image


logger = logging.getLogger(__name__)

__all__ = ['QCamera']


class _Auto:

    '''Sentinel: auto-generate getter/setter from the ``_name`` convention.'''


_AUTO = _Auto()


class QCamera(QtCore.QObject, metaclass=QABCMeta):

    '''Abstract base class for camera devices.

    Provides a unified interface for camera control and image acquisition,
    including thread-safe frame reading, a registration-based property
    system, and context-manager support.

    Subclasses implement :meth:`_initialize`, :meth:`_deinitialize`, and
    :meth:`read`, then call :meth:`registerProperty` and
    :meth:`registerMethod` to expose their adjustable parameters and
    executable actions.  Properties may be registered at any time —
    including inside :meth:`_initialize` — which allows cameras whose
    feature sets are only known after connecting to hardware (e.g.
    GenICam devices) to discover and publish their parameters at
    run-time.

    Registered properties are accessible both through the explicit
    :meth:`get` / :meth:`set` API and as ordinary Python attributes —
    reads (``camera.fps``) and writes (``camera.fps = 30``) are both
    routed through the registered getter and setter.

    A camera has two frame rates, as GenICam does: ``fps`` is the rate that
    was asked for, and :attr:`actualFps` is the rate that the camera
    delivers.  Code that consumes frames, such as a recorder, reads the
    second.

    Parameters
    ----------
    *args :
        Positional arguments forwarded to ``QObject``.
    **kwargs :
        Keyword arguments forwarded to ``QObject``.

    Signals
    -------
    shapeChanged(QSize)
        Emitted with the new shape when setting a property changes the
        image dimensions (see :attr:`shapeProperties`), and by a subclass
        that changes them in some other way.
    propertyValue(str, object)
        Emitted by :meth:`get` with the property name and current value.

    Type Aliases
    ------------
    PropertyValue : bool | int | float | str
        Common type for scalar camera property values.
    Settings : dict[str, PropertyValue]
        Mapping of property name to value, as returned by :meth:`settings`.
    CameraData : tuple[bool, Image | None]
        Return type of :meth:`read`; an ``Image`` is the array of one frame
        (see :mod:`QVideo.lib.videotypes`).

    Notes
    -----
    One reentrant lock serializes access to the device.  Every registered
    getter, setter and method, and :meth:`saferead`, runs holding it, so no
    property is read or written while a frame is being read, and a
    multi-step change (stop acquisition, set, restart) is never interleaved
    with anything else.  Backends need no locking of their own, and may
    freely call one another's properties.

    :meth:`open` and :meth:`close` are *not* serialized with reads: stop
    reading before closing the camera from another thread.  A
    :class:`QVideoSource` does so, because it opens the camera when its
    thread starts and closes it when the thread ends.  Pause and resume
    control is the responsibility of the enclosing :class:`QVideoSource`.
    '''

    PropertyValue = bool | int | float | str
    Settings = dict[str, PropertyValue]
    CameraData = tuple[bool, Image | None]

    #: Emitted with the new shape when the image dimensions change.
    shapeChanged = QtCore.Signal(QtCore.QSize)
    #: Emitted by :meth:`get` with the property name and current value.
    propertyValue = QtCore.Signal(str, object)

    #: The camera's own timestamp for the frame most recently read [s], in
    #: the camera's native clock, or ``None`` if it provides none.  A
    #: subclass sets it in :meth:`read`; the source copies it into the
    #: :class:`~QVideo.lib.videotypes.FrameInfo` of the frame.
    hardwareTimestamp: float | None = None

    #: The values of the pixels that are black and white in the frames, or
    #: ``None`` if the pixels fill the range of their type.  A camera whose
    #: counts have fewer bits than their type, such as 12 bit counts in
    #: ``uint16``, sets it when its pixel format changes, not for each frame;
    #: the source copies it into the
    #: :class:`~QVideo.lib.videotypes.FrameInfo` of each frame.
    levels: tuple[float, float] | None = None

    #: The properties whose setting can change the shape of the frames.
    #: :meth:`set` reads :attr:`shape` before and after the setter of one of
    #: these and emits :attr:`shapeChanged` if it differs, so a backend does
    #: not emit the signal for them.  Aliases resolve (``'width'`` stands for
    #: ``'Width'`` on a GenICam camera).  A backend whose shape depends on
    #: more (a ``resolution`` that sets both) lists it too; a proxy for a
    #: camera that announces its own shape lists none.
    shapeProperties: tuple[str, ...] = ('width', 'height')

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._mutex = threading.RLock()
        #: Other names for registered properties, mapped to the names that
        #: they stand for: a backend whose properties have the names of a
        #: standard (``Width``) can offer the names that every camera
        #: shares (``width``) here.  They work as attributes and in
        #: :meth:`get` and :meth:`set`, but they are not properties.
        self.aliases: dict[str, str] = {}
        #: The registered properties: each name maps to its spec (getter,
        #: setter, type and limits).  Iterate it for the names, which are
        #: the keys of :attr:`settings`.
        self.properties: dict[str, dict[str, object]] = {}
        self._methods: dict[str, Callable[[], object]] = {}
        self._isOpen = False
        self._modelName: str | None = None

    def __enter__(self) -> 'QCamera':
        return self.open()

    def __exit__(self,
                 exc_type: type[BaseException] | None,
                 exc_val: BaseException | None,
                 exc_tb: TracebackType | None) -> None:
        self.close()

    @property
    def actualFps(self) -> float:
        '''Frame rate that the camera delivers [frames per second].

        This is ``fps``, the rate that was asked for, unless a subclass can
        learn what the hardware really does (a camera may deliver less than
        it was asked for, for example when its exposure is long or its
        buffers overrun).  It is read-only: set ``fps``.
        '''
        return self.fps

    def __getattr__(self, name: str) -> object:
        '''Delegate attribute lookup to registered property getters.

        Allows ``camera.fps``, ``camera.width``, etc. to work without
        declaring explicit Python properties for every camera parameter.
        An alias (see :attr:`aliases`) reads the property that it stands
        for.  Only called when normal attribute lookup has already failed.
        '''
        if 'properties' in self.__dict__:
            key = self._canonical(name)
            if key in self.properties:
                return self.properties[key]['getter']()
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value) -> None:
        '''Delegate attribute assignment to registered property setters.

        Routes ``camera.fps = 30`` through :meth:`set` (serialized with
        reads) for any name in ``properties`` or ``aliases``.  All other
        names, including internal backing attributes and Qt object
        attributes, fall through to ``super().__setattr__``.  Whether the
        value is coerced to the type of the property is up to its setter.

        The ``'properties' in self.__dict__`` guard ensures that writes
        during ``__init__`` (before ``properties`` is created) are always
        handled by ``super().__setattr__``.
        '''
        if ('properties' in self.__dict__
                and self._canonical(name) in self.properties):
            self.set(name, value)
        else:
            super().__setattr__(name, value)

    def _canonical(self, name: str) -> str:
        '''Return the property that *name* stands for.'''
        return self.aliases.get(name, name)

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------

    def registerProperty(self,
                         name: str,
                         getter: Callable[[], PropertyValue] | _Auto = _AUTO,
                         setter: (Callable[[PropertyValue], None]
                                  | _Auto | None) = _AUTO,
                         ptype: type[PropertyValue] = float,
                         **meta) -> None:
        '''Register a named camera property.

        By default both getter and setter are auto-generated from the
        ``_name`` backing-attribute convention: the getter reads
        ``self._name`` and the setter writes ``ptype(value)`` back to
        ``self._name``.  Pass an explicit callable to override either,
        or pass ``setter=None`` to make the property read-only.

        Parameters
        ----------
        name : str
            Property name used with :meth:`get`, :meth:`set`, and
            attribute access.
        getter : callable, optional
            Zero-argument callable returning the current value.
            Defaults to ``lambda: getattr(self, f'_{name}')``.
        setter : callable or None, optional
            Single-argument callable applying a new value.  ``None``
            marks the property read-only.  Defaults to
            ``lambda v: setattr(self, f'_{name}', ptype(v))``.
        ptype : type
            Python type of the property value (``int``, ``float``,
            ``bool``, ``str``).  Drives the default setter coercion and
            is stored for use by UI generators such as ``QCameraTree``.
        **meta :
            Additional metadata (e.g. ``minimum``, ``maximum``, ``step``).
            For a ``str`` property, ``limits`` is the list of allowed
            values, which the Qt and Jupyter interfaces present as a
            drop-down.
        '''
        if getter is _AUTO:
            def getter():
                return getattr(self, f'_{name}')
        if setter is _AUTO:
            def setter(value):
                setattr(self, f'_{name}', ptype(value))
        self.properties[name] = dict(
            getter=self._serialized(getter),
            setter=self._serialized(setter),
            ptype=ptype, **meta)

    def registerMethod(self, name: str, method: Callable[[], object]) -> None:
        '''Register a named callable method.

        Parameters
        ----------
        name : str
            Method name used with :meth:`execute`.
        method : callable
            Zero-argument callable to invoke.
        '''
        self._methods[name] = self._serialized(method)

    def _serialized(self, function: Callable | None) -> Callable | None:
        '''Wrap *function* so that it runs holding the device lock.'''
        if function is None:
            return None

        @wraps(function)
        def locked(*args):
            with self._mutex:
                return function(*args)
        return locked

    # ------------------------------------------------------------------
    # Open / close lifecycle
    # ------------------------------------------------------------------

    def open(self, *args, **kwargs) -> 'QCamera':
        '''Open the camera device.

        Calls :meth:`_initialize` only if the device is not already open.

        Returns
        -------
        QCamera
            ``self``, to allow chaining.

        Raises
        ------
        QCameraError
            If a subclass's :meth:`_initialize` reports why the camera
            cannot be opened by raising it, rather than returning
            ``False``.
        '''
        if not self._isOpen:
            self._isOpen = bool(self._initialize(*args, **kwargs))
            if not self._isOpen:
                logger.warning(f'{self.name}: initialization failed')
        return self

    @QtCore.Slot()
    def close(self) -> None:
        '''Close the camera device.

        Safe to call on an already-closed device.  If :meth:`_deinitialize`
        raises, the exception propagates and the camera stays marked open,
        so that closing can be tried again.  Not serialized with reads (see
        the notes of the class).
        '''
        if self._isOpen:
            self._deinitialize()
        self._isOpen = False

    def isOpen(self) -> bool:
        '''Return whether the device is currently open.'''
        return self._isOpen

    @abstractmethod
    def _initialize(self, *args, **kwargs) -> bool:
        '''Configure the device so that :meth:`read` will succeed.

        Subclasses should also call :meth:`registerProperty` and
        :meth:`registerMethod` here for any parameters that are only
        known after the device is opened.

        Returns
        -------
        bool
            ``True`` if initialization succeeded.
        '''

    @abstractmethod
    def _deinitialize(self) -> None:
        '''Release device resources.

        Implement so that deletion or re-opening succeeds.'''

    # ------------------------------------------------------------------
    # Property / method access
    # ------------------------------------------------------------------

    @property
    def methods(self) -> list[str]:
        '''Names of all registered methods.'''
        return list(self._methods.keys())

    @property
    def settings(self) -> Settings:
        '''All registered property values as a name→value dict.

        Reading uses the registered getters directly, to avoid emitting
        :attr:`propertyValue` for each property.  Assigning a dict applies
        each name→value pair through :meth:`set`, in the order of the dict.
        '''
        return {name: spec['getter']()
                for name, spec in self.properties.items()}

    @settings.setter
    def settings(self, settings: Settings) -> None:
        for key, value in settings.items():
            self.set(key, value)

    @QtCore.Slot(str, object)
    def set(self, key: str, value: PropertyValue) -> None:
        '''Set a registered property to the given value.

        If the property is one of :attr:`shapeProperties` and the shape of
        the frames is different afterwards, :attr:`shapeChanged` is emitted
        with the new shape (once, after the setter has finished).  Setting a
        value that leaves the shape as it was emits nothing.

        Parameters
        ----------
        key : str
            Property name.
        value : PropertyValue
            New value to assign.
        '''
        key = self._canonical(key)
        if key not in self.properties:
            logger.error(f'Unknown property: {key}')
            return
        setter = self.properties[key]['setter']
        if setter is None:
            logger.warning(f'Property {key!r} is read-only')
            return
        logger.debug(f'Setting {key}: {value}')
        if not self._affectsShape(key):
            setter(value)
            return
        with self._mutex:
            before = self.shape
            setter(value)
            after = self.shape
        if after != before:
            self.shapeChanged.emit(after)

    def _affectsShape(self, key: str) -> bool:
        '''Return whether setting the property *key* can change the shape.'''
        return any(self._canonical(name) == key
                   for name in self.shapeProperties)

    @QtCore.Slot(str)
    def get(self, key: str) -> PropertyValue | None:
        '''Return the current value of a registered property.

        Emits :attr:`propertyValue` with the name and value.

        Parameters
        ----------
        key : str
            Property name.

        Returns
        -------
        PropertyValue or None
            Current value, or ``None`` if the property is unknown.
        '''
        key = self._canonical(key)
        if key not in self.properties:
            logger.error(f'Unknown property: {key}')
            return None
        value = self.properties[key]['getter']()
        self.propertyValue.emit(key, value)
        return value

    @QtCore.Slot(str)
    def execute(self, key: str) -> None:
        '''Call a registered method by name.

        Parameters
        ----------
        key : str
            Method name.
        '''
        if key in self._methods:
            self._methods[key]()
        else:
            logger.error(f'Unknown method: {key}')

    # ------------------------------------------------------------------
    # Frame acquisition
    # ------------------------------------------------------------------

    @abstractmethod
    def read(self) -> CameraData:
        '''Read one frame from the camera.

        Returns
        -------
        tuple[bool, Image or None]
            ``(True, frame)`` on success, ``(False, None)`` on failure.

        '''

    def saferead(self) -> CameraData:
        '''Read one frame under the camera mutex.

        Blocks any concurrent call to :meth:`set`, :meth:`get`, or
        :meth:`execute` until the frame transfer completes.

        Returns
        -------
        tuple[bool, Image or None]
            Result of :meth:`read`.
        '''
        with self._mutex:
            return self.read()

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        '''Camera name, derived from the concrete class name.'''
        return type(self).__name__

    @property
    def modelName(self) -> str | None:
        '''Hardware-reported camera model name.

        Set by subclasses during :meth:`_initialize` when the device
        reports a human-readable model string (e.g. ``'imx219'`` for a
        Raspberry Pi camera, or a GenICam ``DeviceModelName`` string).
        Returns ``None`` when the hardware does not provide this
        information, in which case :attr:`name` is used as a fallback.
        '''
        return self._modelName

    #: The older spelling of :attr:`modelName`.
    model_name = modelName

    @property
    def shape(self) -> QtCore.QSize:
        '''Image dimensions as ``QSize(width, height)``.

        Returns ``QSize(0, 0)`` if ``width`` or ``height`` is not registered
        or cannot be read at the moment (a getter answers ``None`` for a
        feature that the camera does not allow to read just now).
        '''
        try:
            width = self.properties[self._canonical('width')]['getter']()
            height = self.properties[self._canonical('height')]['getter']()
        except KeyError:
            return QtCore.QSize(0, 0)
        if width is None or height is None:
            return QtCore.QSize(0, 0)
        return QtCore.QSize(int(width), int(height))

    # ------------------------------------------------------------------
    # Hooks for the chooser
    # ------------------------------------------------------------------

    @classmethod
    def precheck(cls) -> None:
        '''Raise now if this camera cannot open for want of a library.

        The chooser calls it before it starts a worker process for the
        camera, so that a machine without the library fails at once, in
        this process, with the message that opening the camera would give.
        The default accepts everything.
        '''

    @classmethod
    def deviceNames(cls) -> dict[int, str]:
        '''Return the names of the devices that the backend can list.

        ``{cameraID: name}`` for the devices that can be named before any
        is opened, or ``{}`` for a backend that cannot (the default), which
        the chooser then knows by its label.
        '''
        return {}

    # ------------------------------------------------------------------
    # Example
    # ------------------------------------------------------------------

    @classmethod
    def example(cls: type['QCamera']) -> None:  # pragma: no cover
        '''Print camera settings and read a few frames.'''
        from pprint import pprint

        camera = cls()
        print(camera.name)
        pprint(camera.settings)
        with camera:
            for _ in range(5):
                print('.' if camera.read()[0] else 'x', end='')
            print('done')


if __name__ == '__main__':  # pragma: no cover
    QCamera.example()
