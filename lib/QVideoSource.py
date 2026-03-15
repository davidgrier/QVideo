from pyqtgraph.Qt import QtCore
from QVideo.lib.QCamera import QCamera
from QVideo.lib.QVideoReader import QVideoReader
import numpy as np
from typing import TypeAlias
import logging


logger = logging.getLogger(__name__)


class QVideoSource(QtCore.QThread):

    '''A threaded video source that reads frames from a camera
    or video file in a separate thread.

    Parameters
    ----------
    source : QCamera | QVideoReader
        The video source to read frames from.

    Signals
    -------
    newFrame(np.ndarray)
        Emitted when a new video frame is available.

    Properties
    ----------
    source : QCamera | QVideoReader
        The video source object.
    fps : float
        Frame rate of the video source [frames per second].
    shape : QSize
        The shape of the video frames (width, height).

    Methods
    -------
    isOpen() -> bool
        Check if the video source is open.
    start() -> QVideoSource
        Start the video source thread.
    stop() -> None
        Stop the video source thread.
    pause() -> None
        Pause video readout.
    resume() -> None
        Resume video readout after pause().
    isPaused() -> bool
        Check if video readout is paused.
    example(*args) -> None
        Demonstrate basic operation of a threaded video source.

    Notes
    -----
    The source is moved to this thread via ``moveToThread`` so that its
    slots are delivered in the capture thread rather than the main thread.
    State variables ``_running`` and ``_paused`` are protected by
    :attr:`mutex`; :attr:`waitcondition` is used to block the capture
    loop while paused and to wake it on :meth:`resume` or :meth:`stop`.
    '''

    Source: TypeAlias = QCamera | QVideoReader

    newFrame = QtCore.pyqtSignal(np.ndarray)

    def __init__(self, source: Source, *args, **kwargs) -> None:
        '''Initialise the video source thread.

        Parameters
        ----------
        source : QCamera | QVideoReader
            The video source to read frames from.  It is moved to this
            thread so that its context manager (open/close) runs in the
            capture thread.
        '''
        super().__init__()
        self.source = source
        self.source.moveToThread(self)
        self.mutex = QtCore.QMutex()
        self.waitcondition = QtCore.QWaitCondition()
        self._paused = False
        self._running = True

    @QtCore.pyqtProperty(QtCore.QVariant)
    def source(self) -> Source:
        '''The underlying QCamera or QVideoReader.'''
        return self._source

    @source.setter
    def source(self, source: Source) -> None:
        self._source = source
        self.shapeChanged = source.shapeChanged

    def isOpen(self) -> bool:
        '''Return whether the source is open.'''
        return self.source.isOpen()

    @QtCore.pyqtProperty(float)
    def fps(self) -> float:
        '''Frame rate of the video source [frames per second].'''
        return self.source.fps

    @QtCore.pyqtProperty(QtCore.QSize)
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
        with self.source:
            while self._running:
                ok = False
                with QtCore.QMutexLocker(self.mutex):
                    if self._paused:
                        self.waitcondition.wait(self.mutex)
                        self._paused = False
                    if not self._running:
                        break
                    ok, frame = self.source.saferead()
                if ok:
                    self.newFrame.emit(frame)
        logger.debug('streaming finished')

    @QtCore.pyqtSlot()
    def start(self) -> 'QVideoSource':
        '''Start the capture thread.

        Returns
        -------
        QVideoSource
            ``self``, to allow chaining (e.g. ``src = QVideoSource(cam).start()``).
        '''
        logger.debug('starting')
        super().start()
        return self

    @QtCore.pyqtSlot()
    def stop(self) -> None:
        '''Stop the capture thread.

        Sets ``_running`` to ``False`` and wakes any thread blocked in
        :meth:`pause`, so that :meth:`run` exits cleanly at the next
        loop iteration.
        '''
        logger.debug('stopping')
        with QtCore.QMutexLocker(self.mutex):
            self._running = False
            self._paused = False
        self.waitcondition.wakeAll()

    @QtCore.pyqtSlot()
    def pause(self) -> None:
        '''Pause frame readout.

        The capture loop will block after the current frame completes.
        Has no effect if the thread is not running.  Call :meth:`resume`
        to continue.
        '''
        logger.debug('pausing')
        with QtCore.QMutexLocker(self.mutex):
            if self._running:
                self._paused = True

    @QtCore.pyqtSlot()
    def resume(self) -> None:
        '''Resume frame readout after :meth:`pause`.'''
        self.waitcondition.wakeAll()

    def isPaused(self) -> bool:
        '''Return ``True`` if the capture loop is currently paused.'''
        return self._paused

    @classmethod
    def example(cls: 'QVideoSource', *args) -> None:  # pragma: no cover
        '''Demonstrate basic operation of a threaded video source.'''
        from pprint import pprint

        source = cls(*args).start()
        print(source.source.name)
        pprint(source.source.settings)
        source.stop()
        source.quit()
        source.wait()
