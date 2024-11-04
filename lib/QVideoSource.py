from PyQt5.QtCore import (QThread, QMutex, QMutexLocker, QWaitCondition,
                          pyqtSlot, pyqtSignal, pyqtProperty)
from QVideo.lib import (QCamera, QReader)
import numpy as np
from typing import (TypeAlias, Optional, Union)
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

    Source: TypeAlias = Union[QCamera, QReader]

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, source: Source, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.source = source
        self.source.moveToThread(self)
        self.mutex = QMutex()
        self.waitcondition = QWaitCondition()
        self._paused = False
        self._running = True

    def isOpen(self) -> bool:
        return self.source.isOpen()

    @pyqtSlot()
    def run(self) -> None:
        logger.debug('streaming started')
        with self.source:
            while self._running:
                with QMutexLocker(self.mutex):
                    if self._paused:
                        self.waitcondition.wait(self.mutex)
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
            self._paused = False
            self.waitcondition.wakeAll()

    def isPaused(self) -> bool:
        '''True if readout is paused'''
        return self._paused

    @classmethod
    def example(cls: 'QVideoSource') -> None:
        '''Demonstrate basic operation of a threaded video source'''
        source = cls().start()
        print(source.source.name)
        pprint(source.source.settings())
        source.stop()
        source.quit()
        source.wait()
