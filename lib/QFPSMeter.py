from PyQt5.QtCore import (QObject, pyqtSignal, pyqtProperty)
import time


class QFPSMeter(QObject):

    fpsReady = pyqtSignal(float)

    def __init__(self, window=10):
        super().__init__()
        self.window = window
        self._value = 0.
        self.count = 0
        self.start = time.time()

    def tick(self):
        self.count += 1
        if (self.count >= self.window):
            now = time.time()
            self._value = self.window / (now - self.start)
            self.fpsReady.emit(self._value)
            self.start = now
            self.count = 0

    @pyqtProperty(float)
    def value(self):
        return self._value
