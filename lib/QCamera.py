from abc import (ABCMeta, abstractmethod)
from PyQt5.QtCore import (QObject, QSize,
                          QMutex, QMutexLocker, QWaitCondition,
                          pyqtSignal, pyqtSlot, pyqtProperty)
import numpy as np
import types
from typing import TypeAlias
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QCameraMeta(type(QObject), ABCMeta):
    pass


class QCamera(QObject, metaclass=QCameraMeta):
    '''Base class for a video camera implementation'''

    PropertyValue: TypeAlias = bool | int | float | str
    Settings: TypeAlias = dict[str, PropertyValue]
    CameraData: TypeAlias = tuple[bool, np.ndarray | None]

    shapeChanged = pyqtSignal(QSize)
    propertyValue = pyqtSignal(str, object)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = self.__class__.__name__
        self.mutex = QMutex()
        self.waitcondition = QWaitCondition()
        self._getInterface()
        self._paused = False
        self._isopen = False

    def __enter__(self) -> bool:
        return self.open()

    def __exit__(self, type, value, traceback) -> None:
        self.close()

    def _getInterface(self) -> None:
        interface = vars(type(self)).items()
        self._properties = [k for k, v in interface
                            if isinstance(v, pyqtProperty)]
        self._methods = [k for k, v in interface
                         if isinstance(v, types.FunctionType)]

    def open(self, *args, **kwargs):
        if not self._isopen:
            self._isopen = self._initialize(*args, **kwargs)
        return self

    @pyqtSlot()
    def close(self) -> None:
        if self._isopen:
            self._deinitialize()
        self._isopen = False

    def isOpen(self) -> bool:
        return self._isopen

    def isPaused(self) -> bool:
        return self._paused

    @abstractmethod
    def _initialize(self, *args, **kwargs) -> bool:
        '''Configure device so that read() will succeed'''
        return True

    @abstractmethod
    def _deinitialize(self) -> None:
        '''Configure device so that either del or open() will succeed'''
        pass

    def properties(self) -> list[str]:
        return self._properties

    def methods(self) -> list[str]:
        return self._methods

    def settings(self) -> Settings:
        return {p: self.get(p) for p in self.properties()}

    def setSettings(self, settings: Settings) -> None:
        for key, value in settings.items():
            self.set(key, value)

    @pyqtSlot(str, object)
    def set(self, key: str, value: PropertyValue) -> None:
        '''Set named property to value'''
        with QMutexLocker(self.mutex):
            logger.debug(f'Setting {key}: {value}')
            if key in self._properties:
                setattr(self, key, value)
            else:
                logger.error(f'Unknown property: {key}')

    @pyqtSlot(str)
    def get(self, key: str) -> PropertyValue | None:
        '''Get named property'''
        with QMutexLocker(self.mutex):
            if key in self._properties:
                value = getattr(self, key)
            else:
                logger.error(f'Unknown property: {key}')
                value = None
            self.propertyValue.emit(key, value)
            return value

    @pyqtSlot(str)
    def execute(self, key: str) -> None:
        '''Execute named method'''
        with QMutexLocker(self.mutex):
            if key in self._methods:
                method = getattr(self, key)
                method(self)
            else:
                logger.error(f'Unknown method: {key}')

    @abstractmethod
    def read(self) -> CameraData:
        return False, None

    def saferead(self) -> CameraData:
        with QMutexLocker(self.mutex):
            if self._paused:
                self.waitcondition.wait(self.mutex)
                self._paused = False
            return self.read()

    @pyqtSlot()
    def pause(self) -> None:
        self._paused = True

    @pyqtSlot()
    def resume(self) -> None:
        self.waitcondition.wakeAll()

    @pyqtProperty(QSize)
    def shape(self) -> QSize:
        return QSize(int(self.width), int(self.height))

    @pyqtProperty(bool)
    @abstractmethod
    def color(self) -> bool:
        return False

    @pyqtProperty(int)
    @abstractmethod
    def width(self) -> int:
        pass

    @width.setter
    @abstractmethod
    def width(self, value: int) -> None:
        self.shapeChanged.emit(self.shape)

    @pyqtProperty(int)
    @abstractmethod
    def height(self) -> int:
        pass

    @height.setter
    @abstractmethod
    def height(self, value: int) -> None:
        self.shapeChanged.emit(self.shape)

    @classmethod
    def example(cls: 'QCamera') -> None:
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
