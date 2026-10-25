'''Worker thread that runs a stack of video filters.'''
from collections import deque
import logging
import numpy as np
from qtpy import QtCore
from QVideo.lib.QVideoFilter import VideoFilter
from QVideo.lib.videotypes import Image, FrameInfo


logger = logging.getLogger(__name__)

__all__ = ['QFilterStack']


class QFilterStack(QtCore.QThread):

    '''Apply a stack of filters to a video source on a worker thread.

    The stack sits between a source and its consumers (a screen, a
    recorder, an overlay).  It receives ``newFrame`` from the source,
    runs the filters in order on its own thread, and emits ``newFrame``
    with the result.  The GUI thread is never involved in the
    computation, and every consumer sees the same filtered stream.

    The :class:`~QVideo.lib.videotypes.FrameInfo` that accompanies each
    frame is passed through unchanged, so a processed frame keeps the
    capture time and index of the frame it came from.

    The stack can stand in for a
    :class:`~QVideo.lib.QVideoSource.QVideoSource`: it has ``newFrame``,
    ``shapeChanged``, ``fps`` and ``shape``.

    **Frames that arrive while the worker is busy.**  The worker holds up
    to *depth* waiting frames.  With the default ``depth=1`` only the
    newest frame waits, so the stack always processes the latest frame
    and an interactive display never lags.  A larger *depth* gives a
    bounded queue for recording.  When the queue is full the oldest
    waiting frame is dropped; drops are counted and reported through
    :attr:`framesDropped`.

    **Failures.**  A filter that raises is logged, removed from the
    stack, and reported through :attr:`filterFailed`; the frame continues
    through the remaining filters unchanged by the failed one.

    **Following a rack.**  With a
    :class:`~QVideo.lib.QFilterRack.QFilterRack` the stack runs the
    rack's switched-on filters, follows the rack as filters are added,
    removed, reordered or toggled, and switches off the rack widget of a
    filter that fails.  The worker thread only ever sees
    :class:`~QVideo.lib.QVideoFilter.VideoFilter` objects, never widgets.

    Filters are plain :class:`~QVideo.lib.QVideoFilter.VideoFilter`
    objects and run on the worker thread, so a filter's parameters
    should be changed by assigning attributes, as the filter widgets do.

    Parameters
    ----------
    source : QVideoSource
        Provider of ``newFrame(ndarray, FrameInfo)``.
    filters : iterable of VideoFilter
        Filters to apply, in order.
    depth : int
        Number of frames that may wait for the worker.  Default: ``1``.
    rack : QFilterRack or None
        Rack whose switched-on filters the stack runs, in place of
        *filters*.

    Notes
    -----
    The stack owns a running thread, so it takes no Qt parent: a parent
    would let Qt delete the thread while it runs.  Keep a reference to
    the stack for as long as it is needed.  The thread stops on
    :meth:`stop`, when the application quits, and when the last
    reference is dropped.

    Signals
    -------
    newFrame(ndarray, FrameInfo)
        A processed frame and the metadata of the frame it came from.
    shapeChanged(QSize)
        The source's frame shape changed.
    framesDropped(int)
        Number of frames dropped since the previous report.
    filterFailed(object, object)
        A filter and the exception it raised.
    '''

    newFrame = QtCore.Signal(np.ndarray, object)
    shapeChanged = QtCore.Signal(QtCore.QSize)
    framesDropped = QtCore.Signal(int)
    filterFailed = QtCore.Signal(object, object)

    def __init__(self,
                 source,
                 filters=(),
                 depth: int = 1,
                 rack=None) -> None:
        super().__init__()
        self._mutex = QtCore.QMutex()
        self._wait = QtCore.QWaitCondition()
        self._queue: deque[tuple[Image, FrameInfo]] = deque(maxlen=depth)
        self._dropped = 0
        self._running = True
        self._filters = tuple(filters)
        self._source = None
        self._rack = None
        self.source = source
        self.rack = rack
        self.start()
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    @property
    def source(self):
        '''The source whose frames are filtered.'''
        return self._source

    @source.setter
    def source(self, source) -> None:
        if self._source is not None:
            self._source.newFrame.disconnect(self._deliver)
            self._source.shapeChanged.disconnect(self.shapeChanged)
        self._source = source
        if source is None:
            return
        source.newFrame.connect(self._deliver, QtCore.Qt.DirectConnection)
        source.shapeChanged.connect(self.shapeChanged)

    @property
    def rack(self):
        '''The rack whose filters the stack runs, or ``None``.'''
        return self._rack

    @rack.setter
    def rack(self, rack) -> None:
        if self._rack is not None:
            self._rack.filtersChanged.disconnect(self._syncRack)
            self.filterFailed.disconnect(self._rack.switchOff)
        self._rack = rack
        if rack is not None:
            rack.filtersChanged.connect(self._syncRack)
            self.filterFailed.connect(rack.switchOff)
            self._syncRack()

    @QtCore.Slot()
    def _syncRack(self) -> None:
        self.filters = self._rack.activeFilters()

    @property
    def filters(self) -> tuple[VideoFilter, ...]:
        '''The filters currently applied, in order.'''
        return self._filters

    @filters.setter
    def filters(self, filters) -> None:
        with QtCore.QMutexLocker(self._mutex):
            self._filters = tuple(filters)

    @property
    def fps(self) -> float:
        '''Frame rate of the source [frames per second].'''
        return self.source.fps

    @property
    def shape(self) -> QtCore.QSize:
        '''Shape of the source frames as ``QSize(width, height)``.'''
        return self.source.shape

    @QtCore.Slot(np.ndarray, object)
    def _deliver(self, frame: Image, info: FrameInfo) -> None:
        '''Queue a frame; runs in the thread that emitted ``newFrame``.'''
        with QtCore.QMutexLocker(self._mutex):
            if not self._running:
                return
            if len(self._queue) == self._queue.maxlen:
                self._dropped += 1
            self._queue.append((frame, info))
        self._wait.wakeOne()

    def run(self) -> None:
        '''Take waiting frames, filter them, and emit the results.'''
        while True:
            with QtCore.QMutexLocker(self._mutex):
                while self._running and not self._queue:
                    self._wait.wait(self._mutex)
                if not self._running:
                    return
                frame, info = self._queue.popleft()
                dropped, self._dropped = self._dropped, 0
            if dropped:
                self.framesDropped.emit(dropped)
            frame = self._apply(frame)
            if frame is not None:
                self.newFrame.emit(frame, info)

    def _apply(self, frame: Image) -> Image | None:
        '''Run *frame* through the filters; ``None`` if a filter has no
        result yet.'''
        for video_filter in self._filters:
            try:
                result = video_filter(frame)
            except Exception as error:
                logger.exception(f'{type(video_filter).__name__} failed '
                                 'and was removed from the filter stack')
                self.filters = [f for f in self._filters
                                if f is not video_filter]
                self.filterFailed.emit(video_filter, error)
                continue
            if result is None:
                return None
            frame = result
        return frame

    def __del__(self) -> None:
        # The garbage collector may get here after Qt has deleted the C++
        # object (or before it was built): then there is no thread to stop.
        try:
            running = self.isRunning()
        except RuntimeError:
            return
        if running:
            self.stop()

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop the worker thread, discarding waiting frames.'''
        with QtCore.QMutexLocker(self._mutex):
            self._running = False
            self._queue.clear()
        self._wait.wakeAll()
        self.wait()
