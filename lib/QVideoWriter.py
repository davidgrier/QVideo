from abc import (ABCMeta, abstractmethod)
from pyqtgraph.Qt.QtCore import (QObject, pyqtSignal, pyqtSlot)
import numpy as np
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoWriterMeta(type(QObject), ABCMeta):
    pass


class QVideoWriter(QObject, metaclass=QVideoWriterMeta):
    '''Abstract base class for saving videos to files'''

    frameNumber = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self,
                 filename: str,
                 fps: int = 24,
                 nframes: int = 10_000,
                 nskip: int = 1,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.filename = filename
        self.fps = fps
        self.framenumber = 0
        self.nskip = nskip
        self.target = nframes
        self.blank = False

    @abstractmethod
    def open(self, frame: np.ndarray) -> bool:
        pass

    @abstractmethod
    def isOpen(self) -> bool:
        return False

    @pyqtSlot(np.ndarray)
    def write(self, frame: np.ndarray) -> None:
        if not self.isOpen():
            if not self.open(frame):
                logger.warning(f'Could not write to {self.filename}')
                self.finished.emit()
            return
        if (self.framenumber >= self.target):
            self.finished.emit()
            return
        if self.framenumber % self.nskip == 0:
            self._write(np.zeros_like(frame) if self.blank else frame)
            self.framenumber += 1
            self.frameNumber.emit(self.framenumber)

    @abstractmethod
    def _write(self, frame: np.ndarray) -> None:
        pass

    @pyqtSlot()
    @abstractmethod
    def close(self) -> None:
        pass
