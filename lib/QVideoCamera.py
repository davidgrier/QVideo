from abc import (ABCMeta, abstractmethod)
from PyQt5.QtCore import (QObject, QMutex, QMutexLocker, QTimer, QSize,
                          pyqtSignal, pyqtSlot, pyqtProperty)
from functools import wraps
import numpy as np
import time
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

    class fpsMeter(QObject):

        fpsReady = pyqtSignal(float)

        def __init__(self):
            super().__init__()
            self.window = 10
            self.count = 0
            self.start = time.time()
            self._value = 0

        def tick(self):
            self.count = (self.count + 1) % self.window
            if (self.count == 0):
                now = time.time()
                self._value = self.window / (now - self.start)
                self.fpsReady.emit(self._value)
                self.start = now

        @pyqtProperty(float)
        def value(self):
            return self._value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mutex = QMutex()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.acquire)
        self.meter = self.fpsMeter()
        self.fpsReady = self.meter.fpsReady
        self._running = False

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

    def read(self):
        return False, None

    def is_running(self):
        return self._running

    @pyqtProperty(object)
    @protected
    def shape(self):
        return QSize(self.width, self.height)

    @pyqtProperty(float)
    @protected
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

    def properties(self):
        return [k for k, v in vars(type(self)).items()
                if isinstance(v, pyqtProperty)]

    def methods(self):
        return [k for k, v in vars(type(self)).items()
                if isinstance(v, types.FunctionType)]
