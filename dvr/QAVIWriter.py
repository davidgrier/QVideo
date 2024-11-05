# -*- coding: utf-8 -*-

from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot)
import numpy as np
import cv2
from typing import Optional


class QAVIWriter(QObject):
    '''Class for saving AVI video files

    Inherits
    --------
    PyQt5.QtCore.QObject
    '''

    frameNumber = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self,
                 filename: str,
                 nframes: int = 10000,
                 nskip: int = 1,
                 fps: int = 24,
                 codec: Optional[str] = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)

        self.filename = filename
        self.nframes = nframes
        self.nskip = nskip
        self.fps = fps
        # NOTE: libavcodec appears to seg fault when
        # recording with the lossless FFV1 codec
        # self.codec = 'FFV1'
        # HuffyYUV 'HFYU' appears to work on both
        # Ubuntu and Macports
        codec = codec or 'HFYU'
        if cv2.__version__.startswith('2.'):
            self.fourcc = cv2.cv.CV_FOURCC(*codec)
            self.BGR2RGB = cv2.cv.CV_COLOR_BGR2RGB
        else:
            self.fourcc = cv2.VideoWriter_fourcc(*codec)
            self.BGR2RGB = cv2.COLOR_BGR2RGB

        self.writer = None
        self.framenumber = 0
        self.shape = None

    def open(self,
             filename: str,
             frame: np.ndarray) -> Optional[cv2.VideoWriter]:
        self.shape = frame.shape
        h, w = self.shape[:2]
        color = len(self.shape) > 2
        args = [filename, self.fourcc, self.fps, (w, h), color]
        writer = cv2.VideoWriter(*args)
        return writer if writer.isOpened() else None

    @pyqtSlot(np.ndarray)
    def write(self, frame: np.ndarray) -> None:
        '''Writes video frame to video file

        Arguments
        ---------
        frame: numpy.ndarray
            Video data to write
        '''
        if self.shape is None:
            self.writer = self.open(self.filename, frame)
            return
        if (self.framenumber >= self.nframes) or (frame.shape != self.shape):
            self.finished.emit()
            return
        if frame.ndim == 3:
            frame = cv2.cvtColor(frame, self.BGR2RGB)
        if self.framenumber % self.nskip == 0:
            self.writer.write(frame)
            self.framenumber += 1
            self.frameNumber.emit(self.framenumber)

    @pyqtSlot()
    def close(self) -> None:
        '''Closes video file'''
        if self.writer is not None:
            self.writer.release()
