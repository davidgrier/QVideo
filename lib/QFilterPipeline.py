'''Video source that runs a pipeline of video filters.'''
from collections import deque
from collections.abc import Iterable
from dataclasses import replace
import logging
from typing import TYPE_CHECKING

import numpy as np
from qtpy import QtCore

from QVideo.lib.QVideoFilter import VideoFilter, prepare
from QVideo.lib.QVideoSource import QVideoSource
from QVideo.lib.videotypes import Image, FrameInfo

if TYPE_CHECKING:
    from QVideo.lib.QFilterRack import QFilterRack


logger = logging.getLogger(__name__)

__all__ = ['QFilterPipeline']


class _FilterStage(QtCore.QObject):

    '''The source that a :class:`QFilterPipeline` runs.

    It stands where a camera stands for a
    :class:`~QVideo.lib.QVideoSource.QVideoSource`: ``saferead`` waits for
    a frame from the upstream source, filters it and returns it.  Frames
    that arrive while it is busy wait in a queue of *depth* frames, and the
    oldest is dropped when the queue is full.
    '''

    shapeChanged = QtCore.Signal(QtCore.QSize)
    framesDropped = QtCore.Signal(int)
    filterFailed = QtCore.Signal(object, object)

    def __init__(self, filters: Iterable[VideoFilter], depth: int) -> None:
        super().__init__()
        self._mutex = QtCore.QMutex()
        self._wait = QtCore.QWaitCondition()
        self._queue: deque[tuple[Image, FrameInfo]] = deque(maxlen=depth)
        self._dropped = 0
        self._open = True
        self._filters = tuple(filters)
        self._upstream: QVideoSource | None = None
        #: Metadata of the frame that ``saferead`` returned last.
        self.info = FrameInfo(0, 0.)

    @property
    def upstream(self) -> 'QVideoSource | None':
        return self._upstream

    @upstream.setter
    def upstream(self, source: 'QVideoSource | None') -> None:
        if self._upstream is not None:
            self._upstream.newFrame.disconnect(self._deliver)
            self._upstream.shapeChanged.disconnect(self.shapeChanged)
        self._upstream = source
        if source is None:
            return
        # The stage lives in a thread without an event loop: a queued
        # connection to it would never be delivered.
        direct = QtCore.Qt.ConnectionType.DirectConnection
        source.newFrame.connect(self._deliver, direct)
        source.shapeChanged.connect(self.shapeChanged, direct)

    @property
    def filters(self) -> tuple[VideoFilter, ...]:
        return self._filters

    @filters.setter
    def filters(self, filters: Iterable[VideoFilter]) -> None:
        with QtCore.QMutexLocker(self._mutex):
            self._filters = tuple(filters)

    @property
    def actualFps(self) -> float:
        return self._upstream.fps if self._upstream is not None else 0.

    @property
    def shape(self) -> QtCore.QSize:
        return (self._upstream.shape if self._upstream is not None
                else QtCore.QSize())

    def isOpen(self) -> bool:
        return self._open

    def __enter__(self) -> '_FilterStage':
        return self

    def __exit__(self, *exc) -> None:
        pass

    def close(self) -> None:
        '''Discard waiting frames and wake a ``saferead`` that waits.'''
        with QtCore.QMutexLocker(self._mutex):
            self._open = False
            self._queue.clear()
        self._wait.wakeAll()

    @QtCore.Slot(np.ndarray, object)
    def _deliver(self, frame: Image, info: FrameInfo) -> None:
        '''Queue a frame; runs in the thread that emitted ``newFrame``.'''
        with QtCore.QMutexLocker(self._mutex):
            if not self._open:
                return
            if len(self._queue) == self._queue.maxlen:
                self._dropped += 1
            self._queue.append((frame, info))
        self._wait.wakeOne()

    def saferead(self) -> tuple[bool, Image | None]:
        '''Return the next filtered frame; ``False`` once closed.

        A frame for which a filter has no result yet (a filter that
        collects frames) is not a result: the call waits for the next one.
        '''
        while True:
            with QtCore.QMutexLocker(self._mutex):
                while self._open and not self._queue:
                    self._wait.wait(self._mutex)
                if not self._open:
                    return False, None
                frame, info = self._queue.popleft()
                dropped, self._dropped = self._dropped, 0
            if dropped:
                self.framesDropped.emit(dropped)
            result, levels = self._apply(frame, info.levels)
            if result is not None:
                self.info = (info if levels == info.levels
                             else replace(info, levels=levels))
                return True, result

    def _apply(self, frame: Image, levels: tuple | None
               ) -> tuple[Image | None, tuple | None]:
        '''Run *frame*, whose pixels have *levels*, through the filters.

        Returns the result and its levels: ``(None, levels)`` if a filter
        has no result yet.
        '''
        for video_filter in self._filters:
            frame, levels = prepare(video_filter, frame, levels)
            try:
                result = video_filter(frame)
            except Exception as error:
                logger.exception(f'{type(video_filter).__name__} failed '
                                 'and was removed from the filter pipeline')
                self.filters = [f for f in self._filters
                                if f is not video_filter]
                self.filterFailed.emit(video_filter, error)
                continue
            if result is None:
                return None, levels
            frame = result
        return frame, levels


class QFilterPipeline(QVideoSource):


    '''Apply a pipeline of filters to a video source on a worker thread.

    The pipeline sits between a source and its consumers (a screen, a
    recorder, an overlay).  It receives ``newFrame`` from the source,
    runs the filters in order on its own thread, and emits ``newFrame``
    with the result.  The GUI thread is never involved in the
    computation, and every consumer sees the same filtered stream.

    The :class:`~QVideo.lib.videotypes.FrameInfo` that accompanies each
    frame is passed through, so a processed frame keeps the capture time and
    index of the frame it came from.

    **Deep frames.**  A ``uint16`` frame from a camera of more than 8 bits
    carries its ``levels`` in the ``FrameInfo``.  A filter that is not
    :attr:`~QVideo.lib.QVideoFilter.VideoFilter.deep` gets the frame
    scaled to ``uint8`` between those levels, and the frames after it have
    no levels.  Filters that are ``deep`` see the counts and keep the levels.

    The pipeline is a :class:`~QVideo.lib.QVideoSource.QVideoSource`
    whose source is the stage that filters, so it has ``newFrame``,
    ``shapeChanged``, ``fps`` and ``shape``, and it is paused, resumed and
    stopped like any other.  :attr:`upstream` is the source that it filters.

    **Frames that arrive while the worker is busy.**  The worker holds up
    to *depth* waiting frames.  With the default ``depth=1`` only the
    newest frame waits, so the pipeline always processes the latest frame
    and an interactive display never lags.  A larger *depth* gives a
    bounded queue for recording.  When the queue is full the oldest
    waiting frame is dropped; drops are counted and reported through
    :attr:`framesDropped`.

    **Failures.**  A filter that raises is logged, removed from the
    pipeline, and reported through :attr:`filterFailed`; the frame continues
    through the remaining filters unchanged by the failed one.

    **Following a rack.**  With a
    :class:`~QVideo.lib.QFilterRack.QFilterRack` the pipeline
    runs the rack's switched-on filters, follows the rack as filters are added,
    removed, reordered or toggled, and switches off the rack widget of a
    filter that fails.  The worker thread only ever sees
    :class:`~QVideo.lib.QVideoFilter.VideoFilter` objects, never widgets.

    Filters are plain :class:`~QVideo.lib.QVideoFilter.VideoFilter`
    objects and run on the worker thread, so a filter's parameters
    should be changed by assigning attributes, as the filter widgets do.

    Parameters
    ----------
    source : QVideoSource or None
        Provider of ``newFrame(ndarray, FrameInfo)``: the
        :attr:`upstream` of the pipeline.
    filters : iterable of VideoFilter
        Filters to apply, in order.
    depth : int
        Number of frames that may wait for the worker.  Default: ``1``.
    rack : QFilterRack or None
        Rack whose switched-on filters the pipeline runs, in place of
        *filters*.

    Notes
    -----
    The pipeline owns a running thread, so it takes no Qt parent: a parent
    would let Qt delete the thread while it runs.  Keep a reference to
    the pipeline for as long as it is needed.  The thread stops on
    :meth:`stop`, when the application quits, and when the last
    reference is dropped.  A stopped pipeline stays stopped.

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

    def __init__(self,
                 source: 'QVideoSource | None',
                 filters: Iterable[VideoFilter] = (),
                 depth: int = 1,
                 rack: 'QFilterRack | None' = None) -> None:
        self._stage = _FilterStage(filters, depth)
        super().__init__(self._stage)  # pyright: ignore[reportArgumentType]
        self.framesDropped = self._stage.framesDropped
        self.filterFailed = self._stage.filterFailed
        self._rack: QFilterRack | None = None
        self.upstream = source
        self.rack = rack
        self.start()
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    @property
    def upstream(self) -> 'QVideoSource | None':
        '''The source whose frames are filtered.'''
        return self._stage.upstream

    @upstream.setter
    def upstream(self, source: 'QVideoSource | None') -> None:
        self._stage.upstream = source

    @property
    def rack(self) -> 'QFilterRack | None':
        '''The rack whose filters the pipeline runs, or ``None``.'''
        return self._rack

    @rack.setter
    def rack(self, rack: 'QFilterRack | None') -> None:
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
        '''Run the filters that the rack has switched on.'''
        if self._rack is not None:     # the rack may be gone by now
            self.filters = self._rack.activeFilters()

    @property
    def filters(self) -> tuple[VideoFilter, ...]:
        '''The filters currently applied, in order.'''
        return self._stage.filters

    @filters.setter
    def filters(self, filters: Iterable[VideoFilter]) -> None:
        self._stage.filters = filters

    def _frameInfo(self) -> FrameInfo:
        '''Return the metadata of the frame that was filtered.'''
        return self._stage.info

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop the worker thread, discarding waiting frames.'''
        super().stop()
        self._stage.close()
        self.wait()
