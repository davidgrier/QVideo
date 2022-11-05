# -*- coding: utf-8 -*-

from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot)
import numpy as np
import cv2
from typing import (Optional, Tuple)

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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
                 shape: Tuple,
                 color: bool,
                 nframes: int = 10000,
                 nskip: int = 1,
                 fps: int = 24,
                 codec: Optional[str] = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)

        self.shape = shape
        self.color = color
        w, h = self.shape.width(), self.shape.height()

        if codec is None:
            # NOTE: libavcodec appears to seg fault when
            # recording with the lossless FFV1 codec
            # codec = 'FFV1'

            # NOTE: HuffyYUV appears to work on both
            # Ubuntu and Macports
            codec = 'HFYU'

        if cv2.__version__.startswith('2.'):
            fourcc = cv2.cv.CV_FOURCC(*codec)
            self.BGR2RGB = cv2.cv.CV_COLOR_BGR2RGB
        else:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            self.BGR2RGB = cv2.COLOR_BGR2RGB

        logger.info(f'Recording: {w}x{h}, color: {color}, fps: {fps}')
        args = [filename, fourcc, fps, (w, h), color]
        self.writer = cv2.VideoWriter(*args)
        self.framenumber = 0
        self.nskip = nskip
        self.target = nframes
        self.frameNumber.emit(self.framenumber)

    def _formatChanged(self, frame: np.ndarray) -> bool:
        color = frame.ndim == 3
        h, w = frame.shape[0:2]
        return ((w != self.shape.width()) or
                (h != self.shape.height()) or
                (color != self.color))

    @pyqtSlot(np.ndarray)
    def write(self, frame: np.ndarray) -> None:
        '''Writes video frame to video file

        Arguments
        ---------
        frame: numpy.ndarray
            Video deata to write
        '''
        if (self.framenumber >= self.target) or self._formatChanged(frame):
            self.finished.emit()
            return
        if self.color:
            frame = cv2.cvtColor(frame, self.BGR2RGB)
        if self.framenumber % self.nskip == 0:
            self.writer.write(frame)
        self.framenumber += 1
        self.frameNumber.emit(self.framenumber)

    @pyqtSlot()
    def close(self) -> None:
        '''Closes video file'''
        self.writer.release()
