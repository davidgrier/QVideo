from pyqtgraph.Qt.QtCore import (QThread,
                                 QMutex, QMutexLocker, QWaitCondition,
                                 pyqtSlot, pyqtSignal, pyqtProperty,
                                 QVariant, QSize)
from .QCamera import QCamera
from .QVideoReader import QVideoReader
import numpy as np
from typing import TypeAlias
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoSource(QThread):

    '''A threaded video source that reads frames from a camera
    or video file in a separate thread.

    Parameters
    ----------
    source : QCamera | QVideoReader
        The video source to read frames from.
    args : list
        Additional positional arguments to pass to the QThread constructor.
    kwargs : dict
        Additional keyword arguments to pass to the QThread constructor.

    Returns
    -------
    QVideoSource : QThread
        The threaded video source object.

    Signals
    -------
    newFrame(np.ndarray)
        Emitted when a new video frame is available.

    Properties
    ----------
    source : QCamera | QVideoReader
        The video source object.
    fps : float
        frame rate of the video source [frames per second].
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
    '''

    Source: TypeAlias = QCamera | QVideoReader

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, source: Source, *args, **kwargs) -> None:
        super().__init__()
        self.source = source
        self.source.moveToThread(self)
        self.mutex = QMutex()
        self.waitcondition = QWaitCondition()
        self._paused = False
        self._running = True

    @pyqtProperty(QVariant)
    def source(self) -> Source:
        return self._source

    @source.setter
    def source(self, source: Source) -> None:
        self._source = source
        self.shapeChanged = source.shapeChanged

    def isOpen(self) -> bool:
        return self.source.isOpen()

    @pyqtProperty(float)
    def fps(self) -> float:
        return self.source.fps

    @pyqtProperty(QSize)
    def shape(self) -> QSize:
        return self.source.shape

    @pyqtSlot()
    def run(self) -> None:
        logger.debug('streaming started')
        with self.source:
            while self._running:
                with QMutexLocker(self.mutex):
                    if self._paused:
                        self.waitcondition.wait(self.mutex)
                        self._paused = False
                    ok, frame = self.source.saferead()
                    if ok:
                        self.newFrame.emit(frame)
        self.finished.emit()
        logger.debug('streaming finished')

    @pyqtSlot()
    def start(self):
        logger.debug('starting')
        super().start()
        return self

    @pyqtSlot()
    def stop(self):
        self.resume()
        logger.debug('stopping')
        if self._running:
            self._running = False

    @pyqtSlot()
    def pause(self) -> None:
        '''Pause video readout'''
        logger.debug('pausing')
        if self._running:
            self._paused = True

    @pyqtSlot()
    def resume(self) -> None:
        '''Resume video readout after pause()'''
        if self._paused:
            self.waitcondition.wakeAll()

    def isPaused(self) -> bool:
        '''True if readout is paused'''
        return self._paused

    @classmethod
    def example(cls: 'QVideoSource', *args) -> None:
        '''Demonstrate basic operation of a threaded video source'''

        from pprint import pprint

        source = cls(*args).start()
        print(source.source.name)
        pprint(source.source.settings())
        source.stop()
        source.quit()
        source.wait()
