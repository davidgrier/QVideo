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

    Camera: TypeAlias = Union[QCamera, QReader]

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, camera: Camera, *args, **kwargs) -> None:
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
        '''Pause video readout

        Arguments
        ---------
        time: int
            Optional: Number of milliseconds to pause video readout.
            If not provided: readout will pause until resume() is called.
        '''
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
        '''Resume video readout after pause()'''
        if self._paused:
            logger.debug('resuming')
            self.waitcondition.wakeAll()

    @pyqtProperty(bool)
    def paused(self) -> bool:
        '''True if readout is paused'''
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        if value:
            self.pause()
        else:
            self.resume()

    @classmethod
    def example(cls: 'QVideoSource') -> None:
        '''Demonstrate basic operation of a threaded video source'''
        source = cls().start()
        print(source.camera.name)
        pprint(source.camera.settings())
        print('pausing ... ', end='')
        source.pause(1000)
        print('done')
        source.stop()
        source.quit()
        source.wait()
