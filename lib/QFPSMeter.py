'''Sliding-window frame-rate meter emitted as a Qt signal.'''
from qtpy import QtCore
from collections import deque
import time
import logging


logger = logging.getLogger(__name__)

__all__ = ['QFPSMeter']


class QFPSMeter(QtCore.QObject):

    '''Measures frame rate over a sliding window of frame timestamps.

    On every :meth:`tick` a timestamp is appended to a circular buffer
    of length *window*.  Once the buffer is full, FPS is computed from
    the span of the buffered timestamps and :attr:`fpsReady` is emitted.
    Because the buffer slides forward one frame at a time, the reading
    updates on every tick rather than in discrete batches.

    Parameters
    ----------
    window : int
        Number of timestamps retained.  Larger values give smoother
        estimates at the cost of slower response to rate changes.
        Values less than 2 are clamped to 2.

    Signals
    -------
    fpsReady(float)
        Emitted on every :meth:`tick` once the buffer is full.

    Properties
    ----------
    value : float
        Most recently measured frame rate [frames per second].
        Zero until the buffer fills for the first time.

    Slots
    -----
    tick() -> None
        Record one frame arrival and update the FPS estimate.
    reset() -> None
        Clear the timestamp buffer and cached value.
    '''

    #: Emitted on every :meth:`tick` once the buffer is full.
    fpsReady = QtCore.Signal(float)

    def __init__(self, window: int = 10) -> None:
        super().__init__()
        self.window = max(2, int(window))
        self._value = 0.
        self._timestamps = deque(maxlen=self.window)

    @QtCore.Slot()
    def tick(self) -> None:
        '''Record one frame arrival and update the FPS estimate.

        Appends the current time to the circular buffer.  Once the
        buffer holds *window* timestamps, computes::

            fps = (window - 1) / (newest_timestamp - oldest_timestamp)

        and emits :attr:`fpsReady`.
        '''
        self._timestamps.append(time.perf_counter())
        if len(self._timestamps) == self.window:
            elapsed = self._timestamps[-1] - self._timestamps[0]
            if elapsed > 0:
                self._value = (self.window - 1) / elapsed
                self.fpsReady.emit(self._value)
            else:
                logger.warning('elapsed time is zero; skipping FPS update')

    @QtCore.Slot()
    def reset(self) -> None:
        '''Reset the meter to its initial state.

        Clears the timestamp buffer and cached value so that the next
        :meth:`tick` begins a fresh measurement.  Useful when the video
        source stops and restarts.
        '''
        self._value = 0.
        self._timestamps.clear()

    @property
    def value(self) -> float:
        '''Most recently measured frame rate [frames per second].'''
        return self._value
