from abc import (ABCMeta, abstractmethod)
from PyQt5.QtCore import (QObject, pyqtProperty, pyqtSlot,
                          pyqtSignal, QSize,
                          QMutex, QMutexLocker, QWaitCondition)
import time
from QVideo.lib import QCamera
import QVideo
from pathlib import Path
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QReaderMeta(type(QObject), ABCMeta):
    pass


class QReader(QObject, metaclass=QReaderMeta):
    '''Base class for a video-file reader'''

    CameraData = QCamera.CameraData

    shapeChanged = pyqtSignal(QSize)

    def __init__(self, filename: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.filename = filename
        self.mutex = QMutex()
        self.waitcondition = QWaitCondition()
        self._paused = False
        self._isopen = False
        self.open()

    def __enter__(self):
        return self.open()

    def __exit__(self, type, value, traceback):
        self.close()

    def open(self, *args, **kwargs):
        if not self._isopen:
            self._isopen = self._initialize(*args, **kwargs)
            if self._isopen:
                self.shapeChanged.emit(self.shape)
        return self

    @pyqtSlot()
    def close(self) -> None:
        if self._isopen:
            self._deinitialize()
        self._isopen = False

    def isOpen(self) -> bool:
        return self._isopen

    def isPaused(self) -> bool:
        return self._paused

    @abstractmethod
    def _initialize(self, *args, **kwargs) -> bool:
        '''Access video file so that read() will succeed'''
        return True

    @abstractmethod
    def _deinitialize(self) -> None:
        '''Close file so that either del or open() will succeed'''
        pass

    @abstractmethod
    def read(self) -> CameraData:
        return False, None

    def saferead(self) -> CameraData:
        with QMutexLocker(self.mutex):
            if self._paused:
                self.waitcondition.wait(self.mutex)
            else:
                self.waitcondition.wait(self.mutex, self.delay)
            return self.read()

    @pyqtSlot()
    def pause(self) -> None:
        self._paused = True

    @pyqtSlot()
    def resume(self) -> None:
        self._paused = False
        self.waitcondition.wakeAll()

    @pyqtProperty(float)
    @abstractmethod
    def fps(self) -> float:
        return 29.97

    @pyqtProperty(int)
    def delay(self) -> int:
        return int(1000./self.fps)

    @pyqtProperty(QSize)
    def shape(self) -> QSize:
        return QSize(int(self.width), int(self.height))

    @pyqtProperty(int)
    @abstractmethod
    def framenumber(self) -> int:
        return 0

    @pyqtProperty(int)
    @abstractmethod
    def width(self) -> int:
        return 0

    @pyqtProperty(int)
    @abstractmethod
    def height(self) -> int:
        return 0

    @pyqtSlot(int)
    @abstractmethod
    def seek(self, framenumber:int) -> None:
        '''Set reader to specified frame number'''
        pass

    @pyqtSlot()
    def rewind(self) -> None:
        self.seek(0)

    @staticmethod
    def examplevideo() -> str:
        path = Path(QVideo.__file__).parent / 'docs' / 'diatom3.avi'
        return str(path)

    @classmethod
    def example(cls: 'QReader') -> None:
        filename = cls.examplevideo()
        video = cls(filename)
        print(filename)
        print(f'{video.length = } frames')
        print(f'{video.width = } pixels')
        print(f'{video.height = } pixels')
        print(f'{video.fps = } fps')
        with video:
            for _ in range(5):
                ok, frame = video.read()
                print(f'{video.framenumber} ', end='')
            print('done')
        with video:
            for _ in range(5):
                ok, frame = video.read()
                print(f'{video.framenumber} ', end='')
            print('done')
