# -*- coding: utf-8 -*-

from QVideo.lib import QVideoWriter
from pyqtgraph.Qt.QtCore import pyqtSlot
import numpy as np
import cv2


class QAVIWriter(QVideoWriter):

    def __init__(self, *args,
                 codec: str | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
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
        self._writer = None
        self._shape = None

    def open(self, frame: np.ndarray) -> None:
        self._shape = frame.shape
        h, w = self._shape[:2]
        color = len(self._shape) > 2
        args = [self.filename, self.fourcc, self.fps, (w, h), color]
        self._writer = cv2.VideoWriter(*args)

    def isOpen(self) -> bool:
        return (self._writer is not None) and self._writer.isOpened()

    def _write(self, frame: np.ndarray) -> None:
        if frame.shape != self._shape:
            self.finished.emit()
            return
        if frame.ndim == 3:
            frame = cv2.cvtColor(frame, self.BGR2RGB)
        self._writer.write(frame)

    @pyqtSlot()
    def close(self) -> None:
        if self.isOpen():
            self._writer.release()
