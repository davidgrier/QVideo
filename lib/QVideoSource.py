'''QThread wrapper that drives a QCamera and emits newFrame signals.'''
import logging
from time import perf_counter
from typing import Any, Protocol, TypeAlias, cast

import numpy as np
from qtpy import QtCore

from QVideo.lib.QCamera import QCamera
from QVideo.lib.QVideoReader import QVideoReader
from QVideo.lib.videotypes import FrameInfo, Image


logger = logging.getLogger(__name__)

#: How long the capture loop waits [ms] before it asks a closed camera again.
_CLOSED_WAIT_MS = 50


class FrameSource(Protocol):

    '''What :class:`QVideoSource` needs of the object that it runs.

    :class:`~QVideo.lib.QCamera.QCamera`,
    :class:`~QVideo.lib.QVideoReader.QVideoReader` and the stage of a
    :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` provide it.  The
    thread opens the source with its context manager, calls
    :meth:`saferead` until it is stopped, and closes it.  A source may
    also have ``seek(framenumber)`` (readers of files), ``lost`` (a signal
    of cameras), ``hardwareTimestamp`` and ``levels``.
    '''

    #: Emitted when the shape of the frames changes (a signal).
    shapeChanged: Any

    @property
    def shape(self) -> QtCore.QSize: ...

    @property
    def actualFps(self) -> float: ...

    def isOpen(self) -> bool: ...

    def saferead(self) -> tuple[bool, Image | None]: ...

    def moveToThread(self, thread: QtCore.QThread | None, /) -> object: ...

    def __enter__(self) -> object: ...

    def __exit__(self, exc_type: Any, exc: Any, tb: Any, /) -> object: ...


VideoSourceType: TypeAlias = FrameSource

__all__ = ['QVideoSource', 'FrameSource', 'VideoSourceType']


class QVideoSource(QtCore.QThread):

    '''A threaded video source that reads frames from a camera
    or video file in a separate thread.

    Parameters
    ----------
    source : FrameSource
        The camera, video reader or filter stage to read frames from.
        The capture thread opens it (its context manager) and closes it
        when the loop ends.

    Signals
    -------
    newFrame(Image, FrameInfo)
        Emitted when a new video frame is available, together with its
        capture metadata.  The :class:`~QVideo.lib.videotypes.FrameInfo`
        is stamped in the capture thread immediately after the frame is
        read.  Slots that need only the frame may accept a single
        argument.
    lost(str)
        The camera has been lost, with the reason: that of the camera
        (:attr:`~QVideo.lib.QCamera.QCamera.lost`), passed on.  The camera
        is closed, and the loop waits for :meth:`stop`.

    Notes
    -----
    The source is moved to this thread with ``moveToThread`` so that its
    slots are delivered in the capture thread rather than the main thread.
    The capture loop blocks on a wait condition while paused, and
    :meth:`resume`, :meth:`seek` and :meth:`stop` wake it.
    '''

    #: Emitted when a new video frame is available.
    newFrame = QtCore.Signal(np.ndarray, object)
    #: Emitted, with the reason, when the camera has been lost.
    lost = QtCore.Signal(str)

    def __init__(self, source: VideoSourceType) -> None:
        super().__init__()
        self._source = source
        self.shapeChanged = source.shapeChanged
        if isinstance(source, QCamera):     # a file cannot be lost
            source.lost.connect(self.lost)
        source.moveToThread(self)
        self._mutex = QtCore.QMutex()
        self._waitCondition = QtCore.QWaitCondition()
        self._paused = False
        self._running = True
        self._seek: int | None = None
        self._frames = 0

    @property
    def source(self) -> VideoSourceType:
        '''The underlying QCamera, QVideoReader or filter stage.'''
        return self._source

    def isOpen(self) -> bool:
        '''Return whether the source is open.'''
        return self.source.isOpen()

    @property
    def fps(self) -> float:
        '''Frame rate that the source delivers [frames per second].

        This is the ``actualFps`` of the camera or reader, not the rate
        that the camera was asked for, so a recorder or a memory budget
        built from it matches the frames that arrive.
        '''
        return self.source.actualFps

    @property
    def shape(self) -> QtCore.QSize:
        '''Shape of the video frames as ``QSize(width, height)``.'''
        return self.source.shape

    def run(self) -> None:
        '''Capture loop: open the source, read frames, emit :attr:`newFrame`.

        Opens the source via its context manager, then loops calling
        :meth:`~QCamera.saferead` and emitting :attr:`newFrame` for each
        successful frame.  The loop blocks when :meth:`pause` is called and
        resumes when :meth:`resume` or :meth:`stop` is called.

        This method is invoked automatically by :meth:`start` in a new
        thread and should not be called directly in production code.
        '''
        logger.debug('streaming started')
        self._frames = 0
        with self.source:
            while True:
                with QtCore.QMutexLocker(self._mutex):
                    while self._paused and self._seek is None:
                        self._waitCondition.wait(self._mutex)
                    if not self._running:
                        break
                    target, self._seek = self._seek, None
                if target is not None:
                    cast(QVideoReader, self.source).seek(target)
                ok, frame = self.source.saferead()
                if ok:
                    info = self._frameInfo()
                    self._frames += 1
                    self.newFrame.emit(frame, info)
                elif not self.source.isOpen():
                    self._waitClosed()
        logger.debug('streaming finished')

    def _waitClosed(self) -> None:
        '''Wait a little, instead of reading, while the camera is closed.

        A camera that was lost has nothing to read, and a loop that asks
        again at once keeps a core busy for nothing.  :meth:`stop` wakes
        the wait, and a camera that is opened again is read again.
        '''
        with QtCore.QMutexLocker(self._mutex):
            if self._running:
                self._waitCondition.wait(self._mutex, _CLOSED_WAIT_MS)

    def _frameInfo(self) -> FrameInfo:
        '''Return the metadata of the frame just read.

        The index counts the frames of this source, the time is now, and
        the hardware timestamp and levels are the camera's, if it has them.
        '''
        return FrameInfo(self._frames, perf_counter(),
                         getattr(self.source, 'hardwareTimestamp', None),
                         getattr(self.source, 'levels', None))

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
    def start(self) -> 'QVideoSource':
        '''Start the capture thread.

        Safe to call after :meth:`stop` / :meth:`wait` to restart the source.
        Resets internal running state before launching the thread so that a
        previously-stopped source can be started again.

        Returns
        -------
        QVideoSource
            ``self``, to allow chaining
            e.g. ``src = QVideoSource(cam).start()``.
        '''
        logger.debug('starting')
        with QtCore.QMutexLocker(self._mutex):
            self._running = True
            self._paused = False
        super().start()
        return self

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop the capture thread and wait for it to finish.

        Wakes a loop that is paused, so that :meth:`run` exits at the next
        iteration, and returns when the thread has ended.  A thread that
        stops itself does not wait for itself.
        '''
        logger.debug('stopping')
        with QtCore.QMutexLocker(self._mutex):
            self._running = False
            self._paused = False
        self._waitCondition.wakeAll()
        self._wakeSource()
        if QtCore.QThread.currentThread() is not self:
            self.wait()

    def _wakeSource(self) -> None:
        '''Wake a source that is blocked in ``saferead``; none is.'''

    @QtCore.Slot()
    def pause(self) -> None:
        '''Pause frame readout.

        The capture loop will block after the current frame completes.
        Has no effect if the thread is not running.  Call :meth:`resume`
        to continue.
        '''
        logger.debug('pausing')
        with QtCore.QMutexLocker(self._mutex):
            if self._running:
                self._paused = True

    @QtCore.Slot()
    def resume(self) -> None:
        '''Resume frame readout after :meth:`pause`.'''
        with QtCore.QMutexLocker(self._mutex):
            self._paused = False
        self._waitCondition.wakeAll()

    @QtCore.Slot(int)
    def seek(self, framenumber: int) -> None:
        '''Read frame *framenumber* next, even while paused.

        The capture loop does the seeking, between two reads, so the
        reader is never touched while it is reading.  A paused source
        delivers that one frame and then stays paused; a running one
        continues from there.  Only readers of video files can seek.

        Parameters
        ----------
        framenumber : int
            Index of the frame to read next (zero-based).
        '''
        with QtCore.QMutexLocker(self._mutex):
            self._seek = framenumber
        self._waitCondition.wakeAll()

    def isPaused(self) -> bool:
        '''Return ``True`` if the capture loop is currently paused.'''
        return self._paused
