# -*- coding: utf-8 -*-

import cv2
from PyQt5.QtCore import (QObject, QTimer, QSize, QRectF,
                          pyqtSignal, pyqtSlot, pyqtProperty)
import numpy as np
from typing import Optional


class QAVIPlayer(QObject):
    '''Video player for AVI files

    Reads frames from a video file,
    emitting newFrame when each frame becomes available.
    '''

    newFrame = pyqtSignal(np.ndarray)

    if cv2.__version__.startswith('2.'):
        SEEK = cv2.cv.CV_CAP_PROP_POS_FRAMES
        WIDTH = cv2.cv.CV_CAP_PROP_FRAME_WIDTH
        HEIGHT = cv2.cv.CV_CAP_PROP_FRAME_HEIGHT
        LENGTH = cv2.cv.CV_CAP_PROP_FRAME_COUNT
        FPS = cv2.cv.CV_CAP_PROP_FPS
        BRG2RGB = cv2.cv.CV_COLOR_BGR2RGB
    else:
        SEEK = cv2.CAP_PROP_POS_FRAMES
        WIDTH = cv2.CAP_PROP_FRAME_WIDTH
        HEIGHT = cv2.CAP_PROP_FRAME_HEIGHT
        LENGTH = cv2.CAP_PROP_FRAME_COUNT
        FPS = cv2.CAP_PROP_FPS
        BRG2RGB = cv2.COLOR_BGR2RGB

    def __init__(self,
                 filename: Optional[str] = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)

        self.running = False

        self.reader = cv2.VideoCapture(filename)
        if self.reader.isOpened():
            self.delay = np.round(1000. / self.fps).astype(int)
            self.width = int(self.reader.get(self.WIDTH))
            self.height = int(self.reader.get(self.HEIGHT))
        else:
            self.close()

    def isOpened(self) -> bool:
        return self.reader is not None

    def close(self) -> None:
        self.reader.release()
        self.reader = None

    def seek(self, frame: int) -> None:
        self.reader.set(self.SEEK, frame)

    @pyqtSlot()
    def emit(self) -> None:
        if not self.running:
            self.close()
            return
        if self.rewinding:
            self.seek(0)
            self.rewinding = False
        if self.emitting:
            ready, self.frame = self.reader.read()
            if ready:
                if self.frame.ndim == 3:
                    self.frame = cv2.cvtColor(self.frame, self.BRG2RGB)
                self.newFrame.emit(self.frame)
            else:
                self.emitting = False
        QTimer.singleShot(self.delay, self.emit)

    @pyqtSlot()
    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.emitting = True
        self.rewinding = False
        self.emit()

    @pyqtSlot()
    def stop(self) -> None:
        self.running = False

    @pyqtSlot()
    def rewind(self) -> None:
        self.rewinding = True

    @pyqtSlot(bool)
    def pause(self, paused: bool) -> None:
        self.emitting = not paused

    def isPaused(self) -> bool:
        return not self.emitting

    @pyqtProperty(QSize)
    def size(self) -> QSize:
        return QSize(self.width, self.height)

    @pyqtProperty(int)
    def length(self) -> int:
        return int(self.reader.get(self.LENGTH))

    @pyqtProperty(int)
    def fps(self) -> int:
        return int(self.reader.get(self.FPS))

    @pyqtProperty(QRectF)
    def roi(self) -> QRectF:
        return QRectF(0., 0., self.width, self.height)
