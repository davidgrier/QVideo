'''Ring buffer that keeps the most recent frames and their capture times.'''
from collections import deque
from time import perf_counter
from qtpy import QtCore
import numpy as np
import psutil
import logging

from QVideo.lib.videotypes import Image, FrameInfo


__all__ = ['QCircularBuffer']


logger = logging.getLogger(__name__)

_MEMORY_WARN_FRACTION = 0.25


class QCircularBuffer(QtCore.QObject):

    '''Ring buffer that keeps the most recent frames and their capture times.

    Each frame appended via :meth:`append` is stored together with its
    :class:`~QVideo.lib.videotypes.FrameInfo`.  When the buffer is full the
    oldest frame is discarded.  :meth:`frames` returns the contents, and
    :attr:`actualFps` the rate at which they were captured.  Writing them
    to a file is the job of
    :class:`~QVideo.dvr.QCircularDVRWidget.QCircularDVRWidget`.

    Parameters
    ----------
    fps : float
        Nominal frame rate used to size the buffer and as a fallback
        fps when fewer than two frames have been captured.
    duration : int
        Buffer length in seconds.  The buffer holds at most
        ``fps × duration`` frames.

    Slots
    -----
    append(frame : numpy.ndarray, info : FrameInfo) -> None
        Add *frame* to the buffer with its capture information.
    '''

    def __init__(self,
                 fps: float = 24.,
                 duration: int = 5,
                 parent=None) -> None:
        super().__init__(parent)
        self._fps = float(fps)
        self._duration = max(1, int(duration))
        self._buffer: deque = deque(
            maxlen=max(1, int(self._fps * self._duration)))
        self._frameBytes: int = 0
        self._warned: bool = False
        self._appended: int = 0

    @property
    def fps(self) -> float:
        '''Nominal frame rate [frames per second].'''
        return self._fps

    @fps.setter
    def fps(self, fps: float) -> None:
        self._fps = float(fps)
        self._resize()

    @property
    def duration(self) -> int:
        '''Buffer length [seconds].'''
        return self._duration

    @duration.setter
    def duration(self, seconds: int) -> None:
        self._duration = max(1, int(seconds))
        self._resize()

    def _resize(self) -> None:
        maxlen = max(1, int(self._fps * self._duration))
        items = list(self._buffer)
        self._buffer = deque(items[-maxlen:], maxlen=maxlen)
        self._warned = False

    def __len__(self) -> int:
        return len(self._buffer)

    def clear(self) -> None:
        '''Discard all buffered frames.'''
        self._buffer.clear()

    @staticmethod
    def _totalRAM() -> int:
        '''Return total physical RAM in bytes.'''
        return psutil.virtual_memory().total

    def _checkMemory(self) -> None:
        self._warned = True
        estimated = self._buffer.maxlen * self._frameBytes
        total = self._totalRAM()
        if estimated > _MEMORY_WARN_FRACTION * total:
            est_mb = estimated / 1024 ** 2
            pct = 100 * estimated / total
            total_gb = total / 1024 ** 3
            logger.warning(
                f'Circular buffer may use {est_mb:.0f} MB '
                f'({pct:.0f}% of {total_gb:.1f} GB RAM); '
                f'consider reducing duration or frame rate.'
            )

    @QtCore.Slot(np.ndarray)
    @QtCore.Slot(np.ndarray, object)
    def append(self, frame: Image, info: FrameInfo | None = None) -> None:
        '''Add *frame* to the buffer with its capture information.

        Parameters
        ----------
        frame : numpy.ndarray
            Video frame to buffer.
        info : FrameInfo, optional
            Capture metadata for *frame*.  If omitted, the frame is
            stamped with the current time.
        '''
        self._frameBytes = frame.nbytes
        if not self._warned:
            self._checkMemory()
        if info is None:
            info = FrameInfo(self._appended, perf_counter())
        self._appended += 1
        self._buffer.append((frame, info))

    def frames(self) -> list[tuple[Image, FrameInfo]]:
        '''Return the buffered ``(frame, info)`` pairs, oldest first.'''
        return list(self._buffer)

    @property
    def actualFps(self) -> float:
        '''Frame rate of the buffered frames, from their capture times.

        This is the nominal :attr:`fps` when the buffer holds fewer than
        two frames, or frames that were all captured at the same time.
        '''
        if len(self._buffer) < 2:
            return self._fps
        elapsed = self._buffer[-1][1].timestamp - self._buffer[0][1].timestamp
        if elapsed <= 0:
            return self._fps
        return (len(self._buffer) - 1) / elapsed
