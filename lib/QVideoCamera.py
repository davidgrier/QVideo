from PyQt5.QtCore import (QObject, QMutex, QSize,
                          pyqtSignal, pyqtSlot, pyqtProperty)
from functools import wraps
import numpy as np
import time
import types
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoCamera(QObject):
    '''Base class for a video camera implementation'''

    newFrame = pyqtSignal(np.ndarray)
    shapeChanged = pyqtSignal()

    def protected(method):
        '''Decorator for preventing clashes in camera operations'''
        @wraps(method)
        def wrapper(inst, *args, **kwargs):
            inst.mutex.lock()
            result = method(inst, *args, **kwargs)
            inst.mutex.unlock()
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
        self.meter = self.fpsMeter()
        self.fpsReady = self.meter.fpsReady

    def run(self):
        logger.debug('Starting video acquisition')
        self._running = True
        while self._running:
            self.mutex.lock()
            ready, frame = self.read()
            if ready:
                self.newFrame.emit(frame)
                self._color = frame.ndim == 3
                self.meter.tick()
            else:
                logger.warning('Frame acquisition failed')
            self.mutex.unlock()
        self.close()
        logger.debug('Video acquisition stopped')

    def read(self):
        return False, None

    @pyqtSlot()
    def stop(self):
        logger.debug('Stopping video acquisition')
        self._running = False

    def close(self):
        logger.debug('Calling default close() method')
        pass

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

    '''
    @pyqtProperty(int)
    def width(self):
        return 640

    @pyqtProperty(int)
    def height(self):
        return 480
    '''

    def properties(self):
        return [k for k, v in vars(type(self)).items()
                if isinstance(v, pyqtProperty)]

    def methods(self):
        return [k for k, v in vars(types(self)).items()
                if isinstance(v, types.FunctionType)]
