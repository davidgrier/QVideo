'''Measure how far the writer of a recording is behind the camera.'''
import math
import numpy as np
import psutil
from qtpy import QtCore
from QVideo.lib.videotypes import Image, FrameInfo


__all__ = ['QBacklogMonitor']

#: Steps in which the backlog is reported.
_STEPS = 20


class QBacklogMonitor(QtCore.QObject):

    '''Measures how far the writer of a recording is behind the camera.

    A recorder must not drop frames, so frames wait in memory while the
    writer is slower than the camera.  The monitor compares the capture
    time of each frame that the camera delivers (a
    :class:`~QVideo.lib.videotypes.FrameInfo`) with that of the newest
    frame that the writer has taken up.  The difference is the backlog, and
    it is measured even while the writer is stuck inside a single write,
    and for sources that capture slowly.

    The monitor does not need a recorder: any object with a ``received``
    attribute, which holds the ``FrameInfo`` of the newest frame that it has
    taken up (``None`` until it has taken one), can be watched, provided that
    it is meant to take every frame.

    The allowance is the smaller of *lagLimit* seconds and the time that the
    camera takes to fill *maxMemory* bytes, so one limit serves both.  The
    monitor only measures: what to do about a recording that falls behind is
    for the application (:class:`~QVideo.dvr.QDVRWidget.QDVRWidget` stops
    it, by default).

    Signals
    -------
    backlog(float)
        Emitted whenever the backlog changes by 5% of the allowance, with
        the backlog as a fraction of it: ``1.`` is the point at which
        ``behind`` is emitted.
    behind(float)
        Emitted once each time the backlog passes the allowance, with the
        lag in seconds.  It is emitted again after the writer has caught up
        and fallen behind anew.
    '''

    #: Emitted as the backlog changes, as a fraction of what is allowed.
    backlog = QtCore.Signal(float)
    #: Emitted when the backlog passes the allowance, with the lag [s].
    behind = QtCore.Signal(float)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._writer = None
        self._fps = 1.
        self._lagLimit = 1.
        self._budget = float('inf')
        self._level = 0

    def start(self,
              writer,
              fps: float,
              lagLimit: float = 1.,
              maxMemory: float | None = None) -> None:
        '''Begin to watch *writer*.

        Parameters
        ----------
        writer : QVideoWriter or object
            The consumer, usually a writer; its ``received`` attribute is
            the :class:`~QVideo.lib.videotypes.FrameInfo` of the newest
            frame that it has taken up.
        fps : float
            Frame rate of the camera [frames per second].
        lagLimit : float
            How far [seconds] the writer may fall behind the newest frame.
        maxMemory : float or None
            Memory [bytes] that the waiting frames may occupy.  ``None``
            means 80% of the memory that is available now.
        '''
        self._writer = writer
        self._fps = fps
        self._lagLimit = lagLimit
        self._budget = maxMemory or 0.8 * psutil.virtual_memory().available
        self._level = 0

    def stop(self) -> None:
        '''Stop watching.  A frame that is delivered late is ignored.'''
        self._writer = None

    @QtCore.Slot(np.ndarray)
    @QtCore.Slot(np.ndarray, object)
    def check(self, frame: Image, info: FrameInfo | None = None) -> None:
        '''Compare the frame that has just been captured with the writer.

        The backlog is reported in steps, not for every frame, and
        ``behind`` once each time that it passes the allowance.
        '''
        taken = self._writer and self._writer.received
        if info is None or not taken:
            return
        lag = max(info.timestamp - taken.timestamp, 0.)
        fill = self._budget / (self._fps * frame.nbytes)
        fraction = lag / min(self._lagLimit, fill)
        level = math.ceil(fraction * _STEPS)
        if level == self._level:
            return
        was, self._level = self._level, level
        self.backlog.emit(fraction)
        if level > _STEPS >= was:
            self.behind.emit(lag)
