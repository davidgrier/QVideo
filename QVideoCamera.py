from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot, QMutex)
from functools import wraps
import numpy as np
import time
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QVideoCamera(QObject):

    newFrame = pyqtSignal(np.ndarray)
    finished = pyqtSignal()
    sizeChanged = pyqtSignal(int)

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

        def tick(self):
            self.count = (self.count + 1) % self.window
            if (self.count == 0):
                now = time.time()
                self.fpsReady.emit(self.window / (now - self.start))
                self.start = now

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
            self.mutex.unlock()
            if ready:
                self.newFrame.emit(frame)
                self.meter.tick()
            else:
                logger.warning('Frame acquisition failed')
        self.close()
        self.finished.emit()
        logger.debug('Video acquisition stopped')

    def read(self):
        return False, None

    @pyqtSlot()
    def stop(self):
        logger.debug('Stopping video acquisition')
        self._running = False

    def close(self):
        pass
