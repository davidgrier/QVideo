# -*- coding: utf-8 -*-

from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot)
import numpy as np
import cv2

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QVideoWriter(QObject):

    frameNumber = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, filename, shape, color,
                 nframes=10000,
                 fps=24,
                 codec=None):
        super(QVideoWriter, self).__init__()

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
        self.target = nframes
        self.frameNumber.emit(self.framenumber)

    def formatChanged(self, frame):
        color = frame.ndim == 3
        h, w = frame.shape[0:2]
        return ((w != self.shape.width()) or
                (h != self.shape.height()) or
                (color != self.color))

    @pyqtSlot(np.ndarray)
    def write(self, frame):
        if self.formatChanged(frame):
            self.finished.emit()
            return
        if self.color:
            frame = cv2.cvtColor(frame, self.BGR2RGB)
        self.writer.write(frame)
        self.framenumber += 1
        self.frameNumber.emit(self.framenumber)

    @pyqtSlot()
    def close(self):
        self.writer.release()
