from pyqtgraph.Qt.QtCore import (QObject,
                                 pyqtSignal, pyqtSlot, pyqtProperty)
import time


class QFPSMeter(QObject):
    '''A frames-per-second (FPS) meter that calculates
    the frame rate over a specified window of frames.

    Inherits
    --------
    QObject
        The base class for all Qt objects.

    Parameters
    ----------
    window : int
        The number of frames over which to calculate the FPS.

    Returns
    -------
    QFPSMeter : QObject
        The FPS meter object.

    Signals
    -------
    fpsReady(float)
        Emitted when a new FPS value is calculated.

    Slots
    -----
    tick() -> None
        Increment the frame count and calculate FPS if
        the window size is reached.

    Properties
    ----------
    value : float
        The current FPS value.
    '''

    fpsReady = pyqtSignal(float)

    def __init__(self,
                 window: int = 10) -> None:
        super().__init__()
        self.window = window
        self._value = 0.
        self.count = 0
        self.start = time.time()

    def __call__(self) -> float:
        return self.value

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
