from pyqtgraph.Qt.QtCore import (QObject, pyqtSignal, pyqtSlot,
                                 pyqtProperty)
import time


class QFPSMeter(QObject):

    fpsReady = pyqtSignal(float)

    def __init__(self,
                 window: int = 10) -> None:
        super().__init__()
        self.window = window
        self._value = 0.
        self.count = 0
        self.start = time.time()

    @pyqtSlot()
    def tick(self) -> None:
        self.count += 1
        if (self.count >= self.window):
            now = time.time()
            self._value = self.window / (now - self.start)
            self.fpsReady.emit(self._value)
            self.start = now
            self.count = 0

    @pyqtProperty(float)
    def value(self) -> float:
        return self._value
