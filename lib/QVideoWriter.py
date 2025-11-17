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
    '''Abstract base class for saving videos to files

    Parameters
    ----------
    filename : str
        The output video filename.
    fps : int
        The frame rate of the output video [frames per second].
    nframes : int
        The maximum number of frames to write.
    nskip : int
        The number of frames to skip between writes.
    kwargs : dict
        Additional keyword arguments to pass to the QObject constructor.

    Returns
    -------
    QVideoWriter : QObject
        The video writer object.

    Signals
    -------
    frameNumber(int)
        Emitted when a new frame is written, providing the
        current frame number.
    finished()
        Emitted when the video writing is finished.

    Slots
    -----
    write(frame: np.ndarray) -> None
        Write a video frame to the file.
    close() -> None
        Close the video file.

    Properties
    ----------
    filename : str
        The output video filename.
    fps : int
        The frame rate of the output video [frames per second].
    nskip : int
        The number of frames to skip between writes.
    nframes : int
        The maximum number of frames to write.

    Abstract Methods
    ----------------
    open(frame: np.ndarray) -> bool
        Open the video file for writing.
    isOpen() -> bool
        Check if the video file is open.
    _write(frame: np.ndarray) -> None
        Write a video frame to the file.
    close() -> None
        Close the video file.
    '''

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
