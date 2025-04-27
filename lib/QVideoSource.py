from pyqtgraph.Qt.QtCore import (QThread, QMutex, QMutexLocker, QWaitCondition,
                                 pyqtSlot, pyqtSignal, pyqtProperty, QVariant,
                                 QSize)
from QVideo.lib import (QCamera, QVideoReader)
from .QVideoReader import QVideoReader
import numpy as np
from typing import TypeAlias
from pprint import pprint
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoSource(QThread):
    '''Read frames from a camera as fast as possible

    The camera object is moved to a background thread
    to prevent interference with the user interface.
    Video frames are returned with the newFrame() signal.
    '''

    Source: TypeAlias = QCamera | QVideoReader

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, source: Source, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
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
        source = cls(*args).start()
        print(source.source.name)
        pprint(source.source.settings())
        source.stop()
        source.quit()
        source.wait()
