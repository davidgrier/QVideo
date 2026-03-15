from abc import ABCMeta, abstractmethod
from pyqtgraph.Qt import QtCore
from numpy.typing import NDArray
import numpy as np
import logging


logger = logging.getLogger(__name__)

_AUTO = object()  # sentinel: auto-generate getter/setter from _name convention


class QCameraMeta(type(QtCore.QObject), ABCMeta):
    pass


class QCamera(QtCore.QObject, metaclass=QCameraMeta):

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
    :meth:`get` / :meth:`set` API and as ordinary Python attributes
    (``camera.fps``, ``camera.width``, etc.) via ``__getattr__``.

    Parameters
    ----------
    *args :
        Positional arguments forwarded to ``QObject``.
    **kwargs :
        Keyword arguments forwarded to ``QObject``.

    Signals
    -------
    shapeChanged(QSize)
        Emitted by subclasses when the image dimensions change.
    propertyValue(str, object)
        Emitted by :meth:`get` with the property name and current value.

    Type Aliases
    ------------
    PropertyValue : bool | int | float | str
        Common type for scalar camera property values.
    Settings : dict[str, PropertyValue]
        Mapping of property name to value, as returned by :meth:`settings`.
    Image : NDArray[np.uint8]
        A single camera frame.
    CameraData : tuple[bool, Image | None]
        Return type of :meth:`read`.

    Notes
    -----
    ``QCamera`` holds a single non-recursive :attr:`mutex`.  :meth:`set`,
    :meth:`get`, :meth:`execute`, and :meth:`saferead` all acquire it,
    so subclass :meth:`read` implementations must not call back into
    any of those methods or a deadlock will result.  Pause and resume
    control is the responsibility of the enclosing :class:`QVideoSource`.
    '''

    PropertyValue = bool | int | float | str
    Settings = dict[str, PropertyValue]
    Image = NDArray[np.uint8]
    CameraData = tuple[bool, Image | None]

    shapeChanged = QtCore.pyqtSignal(QtCore.QSize)
    propertyValue = QtCore.pyqtSignal(str, object)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.mutex = QtCore.QMutex()
        self._properties: dict = {}
        self._methods: dict = {}
        self._isopen = False

    def __enter__(self) -> 'QCamera':
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __getattr__(self, name: str):
        '''Delegate attribute lookup to registered property getters.

        Allows ``camera.fps``, ``camera.width``, etc. to work without
        declaring explicit Python properties for every camera parameter.
        Only called when normal attribute lookup has already failed.
        '''
        if ('_properties' in self.__dict__ and
                name in self._properties):
            return self._properties[name]['getter']()
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'")

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------

    def registerProperty(self, name: str, getter=_AUTO,
                         setter=_AUTO, ptype=float, **meta) -> None:
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
        '''
        if getter is _AUTO:
            def getter(): return getattr(self, f'_{name}')
        if setter is _AUTO:
            def setter(v): return setattr(self, f'_{name}', ptype(v))
        self._properties[name] = dict(
            getter=getter, setter=setter, ptype=ptype, **meta)

    def registerMethod(self, name: str, method) -> None:
        '''Register a named callable method.

        Parameters
        ----------
        name : str
            Method name used with :meth:`execute`.
        method : callable
            Zero-argument callable to invoke.
        '''
        self._methods[name] = method

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
        '''
        if not self._isopen:
            self._isopen = bool(self._initialize(*args, **kwargs))
            if not self._isopen:
                logger.warning(f'{self.name}: initialization failed')
        return self

    @QtCore.pyqtSlot()
    def close(self) -> None:
        '''Close the camera device.

        Safe to call on an already-closed device.
        '''
        if self._isopen:
            self._deinitialize()
        self._isopen = False

    def isOpen(self) -> bool:
        '''Return whether the device is currently open.'''
        return self._isopen

    @abstractmethod
    def _initialize(self, *args, **kwargs) -> bool:
        '''Configure the device so that :meth:`read` will succeed.

        Subclasses should also call :meth:`registerProperty` and
        :meth:`registerMethod` here for any parameters that are only
        known after the device is opened.

        Returns
        -------
        bool
            ``True`` if initialisation succeeded.
        '''

    @abstractmethod
    def _deinitialize(self) -> None:
        '''Release device resources.

        Implement so that deletion or re-opening succeeds.'''

    # ------------------------------------------------------------------
    # Property / method access
    # ------------------------------------------------------------------

    @property
    def properties(self) -> list[str]:
        '''Names of all registered properties.'''
        return list(self._properties.keys())

    @property
    def methods(self) -> list[str]:
        '''Names of all registered methods.'''
        return list(self._methods.keys())

    @property
    def settings(self) -> Settings:
        '''All registered property values as a name→value dict.

        Uses registered getters directly to avoid emitting
        :attr:`propertyValue` for each property.
        '''
        return {name: spec['getter']()
                for name, spec in self._properties.items()}

    @settings.setter
    def settings(self, settings: Settings) -> None:
        '''Apply a dict of property name→value pairs via :meth:`set`.

        Parameters
        ----------
        settings : Settings
            Properties to apply.
        '''
        for key, value in settings.items():
            self.set(key, value)

    @QtCore.pyqtSlot(str, object)
    def set(self, key: str, value: PropertyValue) -> None:
        '''Set a registered property to the given value.

        Parameters
        ----------
        key : str
            Property name.
        value : PropertyValue
            New value to assign.
        '''
        with QtCore.QMutexLocker(self.mutex):
            if key not in self._properties:
                logger.error(f'Unknown property: {key}')
                return
            setter = self._properties[key]['setter']
            if setter is None:
                logger.warning(f'Property {key!r} is read-only')
            else:
                logger.debug(f'Setting {key}: {value}')
                setter(value)

    @QtCore.pyqtSlot(str)
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
        with QtCore.QMutexLocker(self.mutex):
            if key in self._properties:
                value = self._properties[key]['getter']()
            else:
                logger.error(f'Unknown property: {key}')
                return None
        self.propertyValue.emit(key, value)
        return value

    @QtCore.pyqtSlot(str)
    def execute(self, key: str) -> None:
        '''Call a registered method by name.

        Parameters
        ----------
        key : str
            Method name.
        '''
        with QtCore.QMutexLocker(self.mutex):
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

        Notes
        -----
        Must not call :meth:`set`, :meth:`get`, :meth:`execute`, or
        :meth:`saferead` — those methods acquire the same non-recursive
        mutex that :meth:`saferead` holds while invoking ``read()``.
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
        with QtCore.QMutexLocker(self.mutex):
            return self.read()

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        '''Camera name, derived from the concrete class name.'''
        return type(self).__name__

    @property
    def shape(self) -> QtCore.QSize:
        '''Image dimensions as ``QSize(width, height)``.

        Returns ``QSize(0, 0)`` if ``width`` or ``height`` are not
        registered.
        '''
        try:
            w = self._properties['width']['getter']()
            h = self._properties['height']['getter']()
        except KeyError:
            return QtCore.QSize(0, 0)
        return QtCore.QSize(int(w), int(h))

    # ------------------------------------------------------------------
    # Example
    # ------------------------------------------------------------------

    @classmethod
    def example(cls) -> None:  # pragma: no cover
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
