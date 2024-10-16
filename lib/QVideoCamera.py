from abc import (ABCMeta, abstractmethod)
from PyQt5.QtCore import (QObject, QSize, pyqtSignal, pyqtSlot, pyqtProperty)
import numpy as np
import types
from typing import (TypeAlias, Union)
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


Value: TypeAlias = Union[bool, int, float, str]


class QCameraMeta(type(QObject), ABCMeta):
    pass


class QCamera(QObject, metaclass=QCameraMeta):
    '''Base class for a video camera implementation'''

    shapeChanged = pyqtSignal(QSize)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._getInterface()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def _getInterface(self) -> None:
        interface = vars(type(self)).items()
        self._properties = [k for k, v in interface
                            if isinstance(v, pyqtProperty)]
        self._methods = [k for k, v in interface
                         if isinstance(v, types.FunctionType)]

    @abstractmethod
    def open(self) -> None:
        '''Acquire interface to camera so that it is ready to read'''
        pass

    @pyqtSlot()
    @abstractmethod
    def close(self) -> None:
        '''Perform clean-up operations at closing'''
        pass

    def properties(self) -> list[str]:
        return self._properties

    def methods(self) -> list[str]:
        return self._methods

    def settings(self) -> dict[str, Value]:
        return {p: self.get(p) for p in self.properties()}

    def setSettings(self, settings: dict[str, Value]) -> None:
        for key, value in settings.items():
            self.set(key, value)

    @pyqtSlot(str, object)
    def set(self, key: str, value) -> None:
        '''Set named property to value'''
        logger.debug(f'Setting {key}: {value}')
        if key in self._properties:
            setattr(self, key, value)
        else:
            logger.error(f'Unknown property: {key}')

    def get(self, key: str) -> Value:
        '''Get named property'''
        if key in self._properties:
            return getattr(self, key)
        else:
            logger.error(f'Unknown property: {key}')
            return None

    @pyqtSlot(str)
    def execute(self, key: str) -> None:
        '''Execute named method'''
        if key in self._methods:
            method = getattr(self, key)
            method(self)
        else:
            logger.error(f'Unknown method: {key}')

    @abstractmethod
    def read(self) -> tuple[bool, np.ndarray]:
        return False, None

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
