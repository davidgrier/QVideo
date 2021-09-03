from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot, pyqtProperty)
import numpy as np
import time
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


class QVideoCamera(QObject):

    newFrame = pyqtSignal(np.ndarray)
    finished = pyqtSignal()

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
        self.meter = self.fpsMeter()
        self.fpsReady = self.meter.fpsReady

    def run(self):
        logger.debug('Starting acquisition')
        self._running = True
        while self._running:
            ready, frame = self.read()
            if ready:
                self.newFrame.emit(frame)
                self.meter.tick()
            else:
                logger.warning('Failed to read frame')
        logger.debug('Ending acquisition')
        self.close()
        self.finished.emit()

    def read(self):
        return False, None

    @pyqtSlot()
    def stop(self):
        self._running = False

    def close(self):
        pass
