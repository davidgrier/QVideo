from abc import (ABCMeta, abstractmethod)
from PyQt5.QtCore import (QObject, QMutex, QMutexLocker, QTimer, QSize,
                          pyqtSignal, pyqtSlot, pyqtProperty)
from functools import wraps
from QVideo.lib.QFPSMeter import QFPSMeter
import numpy as np
import types
from typing import Any
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoCameraMeta(type(QObject), ABCMeta):
    pass


class QVideoCamera(QObject, metaclass=QVideoCameraMeta):
    '''Base class for a video camera implementation'''

    newFrame = pyqtSignal(np.ndarray)
    shapeChanged = pyqtSignal()

    def protected(method):
        '''Decorator for preventing clashes in camera operations'''
        @wraps(method)
        def wrapper(inst, *args, **kwargs):
            with QMutexLocker(inst.mutex):
                result = method(inst, *args, **kwargs)
            return result
        return wrapper

    def __setattr__(self, prop: str, val: Any) -> None:
        super().__setattr__(prop, val)
        if prop in ['width', 'height']:
            self.shapeChanged.emit()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._getInterface()
        self.mutex = QMutex()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.acquire)
        self.meter = QFPSMeter()
        self._running = False

    def _getInterface(self):
        interface = vars(type(self)).items()
        self._properties = [k for k, v in interface
                            if isinstance(v, pyqtProperty)]
        self._methods = [k for k, v in interface
                         if isinstance(v, types.FunctionType)]

    def properties(self):
        return self._properties

    def methods(self):
        return self._methods

    @pyqtSlot(str, object)
    def set(self, key, value):
        '''Set named property to value'''
        if key in self._properties:
            setattr(self, key, value)
        else:
            logger.error(f'Unknown property: {key}')

    def get(self, key):
        '''Get named property'''
        if key in self._properties:
            return getattr(self, key)
        else:
            logger.error(f'Unknown property: {key}')
            return None

    @pyqtSlot(str)
    def execute(self, key):
        '''Execute named method'''
        if key in self._methods:
            method = getattr(self, key)
            method(self)
        else:
            logger.error(f'Unknown method: {key}')

    @pyqtSlot()
    def start(self):
        '''Start video acquisition'''
        logger.debug('Starting video acquisition')
        self._running = True
        self.timer.start(1)

    @pyqtSlot()
    def stop(self):
        '''Stop video acquisition

        Acquisition can be restarted with a call to start()
        '''
        logger.debug('Stopping video acquisition')
        self._running = False

    @pyqtSlot()
    def close(self):
        '''Perform clean-up operations at closing

        This slot should be overridden by subclasses
        '''
        logger.debug('Calling default close() method')

    @pyqtSlot()
    def acquire(self):
        with QMutexLocker(self.mutex):
            ready, frame = self.read()
        if ready:
            self.newFrame.emit(frame)
            self._color = frame.ndim == 3
            self.meter.tick()
            if self._running:
                self.timer.start(1)
        else:
            logger.warning('Frame acquisition failed')

    @abstractmethod
    def read(self):
        return False, None

    def is_running(self):
        return self._running

    @pyqtProperty(object)
    @protected
    def shape(self):
        return QSize(int(self.width), int(self.height))

    @pyqtProperty(float)
    def fps(self):
        return self.meter.value

    @pyqtProperty(bool)
    def color(self):
        return self._color

    @pyqtProperty(int)
    @abstractmethod
    def width(self):
        pass

    @width.setter
    @abstractmethod
    def width(self, value):
        pass

    @pyqtProperty(int)
    @abstractmethod
    def height(self):
        pass

    @height.setter
    @abstractmethod
    def height(self, value):
        pass
