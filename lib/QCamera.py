from abc import ABCMeta, abstractmethod
from pyqtgraph.Qt import QtCore
from numpy.typing import NDArray
from typing import TypeAlias
import numpy as np
import types
import logging


logger = logging.getLogger(__name__)


class QCameraMeta(type(QtCore.QObject), ABCMeta):
    pass


class QCamera(QtCore.QObject, metaclass=QCameraMeta):

    '''Abstract base class for camera devices.

    Provides a unified interface for camera control and image acquisition,
    including thread-safe frame reading, property management, and
    context-manager support.

    Subclasses must implement :meth:`_initialize`, :meth:`_deinitialize`,
    :meth:`read`, and the abstract properties ``color``, ``width``,
    ``height``, and ``fps``.

    Parameters
    ----------
    *args :
        Positional arguments forwarded to ``QObject``.
    **kwargs :
        Keyword arguments forwarded to ``QObject``.

    Signals
    -------
    shapeChanged(QSize)
        Emitted when the camera image dimensions change.
    propertyValue(str, object)
        Emitted by :meth:`get` with the property name and its current value.

    Type Aliases
    ------------
    PropertyValue : bool | int | float | str
        Valid type for a camera property value.
    Settings : dict[str, PropertyValue]
        Mapping of property name to value.
    Image : NDArray[np.uint8]
        A camera image frame.
    CameraData : tuple[bool, Image | None]
        Return type of :meth:`read`: success flag and frame (or ``None``).
    '''

    PropertyValue: TypeAlias = bool | int | float | str
    Settings: TypeAlias = dict[str, PropertyValue]
    Image: TypeAlias = NDArray[np.uint8]
    CameraData: TypeAlias = tuple[bool, Image | None]

    shapeChanged = QtCore.pyqtSignal(QtCore.QSize)
    propertyValue = QtCore.pyqtSignal(str, object)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = self.__class__.__name__
        self.mutex = QtCore.QMutex()
        self.waitcondition = QtCore.QWaitCondition()
        self._getInterface()
        self._paused = False
        self._isopen = False

    def __enter__(self) -> 'QCamera':
        return self.open()

    def __exit__(self, type, value, traceback) -> None:
        self.close()

    def _getInterface(self) -> None:
        interface = vars(type(self)).items()
        self._properties = [k for k, v in interface
                            if isinstance(v, QtCore.pyqtProperty)]
        self._methods = [k for k, v in interface
                         if isinstance(v, types.FunctionType)]

    def open(self, *args, **kwargs) -> 'QCamera':
        '''Open the camera device.

        Calls :meth:`_initialize` only if the device is not already open.

        Parameters
        ----------
        *args :
            Forwarded to :meth:`_initialize`.
        **kwargs :
            Forwarded to :meth:`_initialize`.

        Returns
        -------
        QCamera
            ``self``, to allow chaining (e.g. ``camera.open().read()``).
        '''
        if not self._isopen:
            self._isopen = self._initialize(*args, **kwargs)
        return self

    @QtCore.pyqtSlot()
    def close(self) -> None:
        '''Close the camera device.

        Calls :meth:`_deinitialize` only if the device is currently open.
        Safe to call on an already-closed device.
        '''
        if self._isopen:
            self._deinitialize()
        self._isopen = False

    def isOpen(self) -> bool:
        '''Return whether the camera device is currently open.'''
        return self._isopen

    def isPaused(self) -> bool:
        '''Return whether the camera is in a paused state.'''
        return self._paused

    @abstractmethod
    def _initialize(self, *args, **kwargs) -> bool:
        '''Configure the device so that :meth:`read` will succeed.

        Returns
        -------
        bool
            ``True`` if initialisation succeeded.
        '''
        return True

    @abstractmethod
    def _deinitialize(self) -> None:
        '''Release device resources so that deletion or re-opening succeeds.'''

    def properties(self) -> list[str]:
        '''Return the names of all registered camera properties.'''
        return self._properties

    def methods(self) -> list[str]:
        '''Return the names of all registered camera methods.'''
        return self._methods

    def settings(self) -> Settings:
        '''Return all property values as a name→value dict.'''
        return {p: self.get(p) for p in self.properties()}

    def setSettings(self, settings: Settings) -> None:
        '''Apply a dict of property name→value pairs.

        Parameters
        ----------
        settings : Settings
            Properties to set.
        '''
        for key, value in settings.items():
            self.set(key, value)

    @QtCore.pyqtSlot(str, object)
    def set(self, key: str, value: PropertyValue) -> None:
        '''Set a named property to the given value.

        Parameters
        ----------
        key : str
            Property name.
        value : PropertyValue
            New value to assign.
        '''
        with QtCore.QMutexLocker(self.mutex):
            logger.debug(f'Setting {key}: {value}')
            if key in self._properties:
                setattr(self, key, value)
            else:
                logger.error(f'Unknown property: {key}')

    @QtCore.pyqtSlot(str)
    def get(self, key: str) -> PropertyValue | None:
        '''Return the current value of a named property.

        Emits :attr:`propertyValue` with the name and value.

        Parameters
        ----------
        key : str
            Property name.

        Returns
        -------
        PropertyValue or None
            Current property value, or ``None`` if the property is unknown.
        '''
        with QtCore.QMutexLocker(self.mutex):
            if key in self._properties:
                value = getattr(self, key)
            else:
                logger.error(f'Unknown property: {key}')
                value = None
            self.propertyValue.emit(key, value)
            return value

    @QtCore.pyqtSlot(str)
    def execute(self, key: str) -> None:
        '''Call a named method on the camera.

        Parameters
        ----------
        key : str
            Method name.
        '''
        with QtCore.QMutexLocker(self.mutex):
            if key in self._methods:
                method = getattr(self, key)
                method(self)
            else:
                logger.error(f'Unknown method: {key}')

    @abstractmethod
    def read(self) -> CameraData:
        '''Read one frame from the camera.

        Returns
        -------
        tuple[bool, Image or None]
            ``(True, frame)`` on success, ``(False, None)`` on failure.
        '''
        return False, None

    def saferead(self) -> CameraData:
        '''Read a frame, blocking if the camera is paused.

        Acquires the mutex before reading. If the camera is paused,
        waits on :attr:`waitcondition` until :meth:`resume` is called.

        Returns
        -------
        tuple[bool, Image or None]
            Result of :meth:`read`.
        '''
        with QtCore.QMutexLocker(self.mutex):
            if self._paused:
                self.waitcondition.wait(self.mutex)
                self._paused = False
            return self.read()

    @QtCore.pyqtSlot()
    def pause(self) -> None:
        '''Signal that the next :meth:`saferead` should block.'''
        self._paused = True

    @QtCore.pyqtSlot()
    def resume(self) -> None:
        '''Wake any thread blocked in :meth:`saferead`.'''
        self.waitcondition.wakeAll()

    @QtCore.pyqtProperty(QtCore.QSize)
    def shape(self) -> QtCore.QSize:
        '''Image dimensions as ``QSize(width, height)``.'''
        return QtCore.QSize(int(self.width), int(self.height))

    @QtCore.pyqtProperty(bool)
    @abstractmethod
    def color(self) -> bool:
        '''``True`` if the camera delivers colour frames.'''
        return False

    @QtCore.pyqtProperty(int, notify=shapeChanged)
    @abstractmethod
    def width(self) -> int:
        '''Image width in pixels.'''

    @width.setter
    @abstractmethod
    def width(self, value: int) -> None:
        self.shapeChanged.emit(self.shape)

    @QtCore.pyqtProperty(int, notify=shapeChanged)
    @abstractmethod
    def height(self) -> int:
        '''Image height in pixels.'''

    @height.setter
    @abstractmethod
    def height(self, value: int) -> None:
        self.shapeChanged.emit(self.shape)

    @QtCore.pyqtProperty(float)
    @abstractmethod
    def fps(self) -> float:
        '''Frame rate in frames per second.'''

    @fps.setter
    @abstractmethod
    def fps(self, fps: float) -> None:
        pass

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Print camera settings and read a few frames.'''
        from pprint import pprint

        logger.setLevel(logging.ERROR)
        camera = cls()
        print(camera.name)
        pprint(camera.settings())
        with camera:
            for n in range(5):
                print('.' if camera.read()[0] else 'x', end='')
            else:
                print('done')
        with camera:
            for n in range(5):
                print('.' if camera.read()[0] else 'x', end='')
            else:
                print('done')


if __name__ == '__main__':  # pragma: no cover
    QCamera.example()
