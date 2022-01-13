from abc import (ABCMeta, abstractmethod)
from PyQt5.QtCore import (QObject, QMutex, QMutexLocker, QTimer, QSize,
                          pyqtSignal, pyqtSlot, pyqtProperty)
from functools import wraps
from QVideo.lib.QFPSMeter import QFPSMeter
import numpy as np
import types
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._getProperties()
        self._getMethods()
        self.mutex = QMutex()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.acquire)
        self.meter = QFPSMeter()
        self._running = False

    def _getProperties(self):
        self._properties = [k for k, v in vars(type(self)).items()
                            if isinstance(v, pyqtProperty)]

    def _getMethods(self):
        self._methods = [k for k, v in vars(type(self)).items()
                         if isinstance(v, types.FunctionType)]

    def properties(self):
        return self._properties

    def methods(self):
        return self._methods

    @pyqtSlot(str, object)
    def set(self, name, value):
        '''Set named property to value'''
        if name in self._properties:
            setattr(self, name, value)

    def get(self, name):
        '''Get named property'''
        if name in self._properties:
            getattr(self, name)

    @pyqtSlot(str)
    def execute(self, name):
        '''Execute named method'''
        if name in self._methods:
            method = getattr(self, name)
            return method(self)

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
    @abstractmethod
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
        return QSize(self.width, self.height)

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
