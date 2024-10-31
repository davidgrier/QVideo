from PyQt5.QtCore import (QThread, QMutex, QMutexLocker, QWaitCondition,
                          pyqtSlot, pyqtSignal, pyqtProperty)
from QVideo.lib import QCamera
import numpy as np
from typing import Optional
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QVideoSource(QThread):

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, camera: QCamera, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.camera = camera
        self.camera.moveToThread(self)
        self.mutex = QMutex()
        self.waitcondition = QWaitCondition()
        self._running = True
        self._paused = False

    @pyqtSlot()
    def run(self) -> None:
        logger.debug('streaming started')
        with self.camera:
            while self._running:
                with QMutexLocker(self.mutex):
                    ok, frame = self.camera.saferead()
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
        with QMutexLocker(self.mutex):
            if self._running:
                self._running = False

    @pyqtSlot()
    def pause(self, time: Optional[int] = None) -> None:
        if self._paused:
            return
        logger.debug('pausing')
        with QMutexLocker(self.mutex):
            logger.debug('paused')
            self._paused = True
            if time is None:
                self.waitcondition.wait(self.mutex)
            else:
                self.waitcondition.wait(self.mutex, time)
            self._paused = False
            logger.debug('resumed')

    @pyqtSlot()
    def resume(self):
        if self._paused:
            logger.debug('resuming')
            self.waitcondition.wakeAll()

    @pyqtProperty(bool)
    def paused(self) -> bool:
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        if value:
            self.pause()
        else:
            self.resume()
