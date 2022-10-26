# -*- coding: utf-8 -*-

"""QVideoPlayer.py: pyqtgraph module for OpenCV video playback."""

import cv2
from PyQt5.QtCore import (QObject, QTimer, QSize, QRectF,
                          pyqtSignal, pyqtSlot, pyqtProperty)
import numpy as np


class QVideoPlayer(QObject):
    '''OpenCV video player

    Continuously reads frames from a video file,
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

    def __init__(self, filename=None):
        super(QVideoPlayer, self).__init__()

        self.running = False

        self.capture = cv2.VideoCapture(filename)
        if self.capture.isOpened():
            self.delay = np.round(1000. / self.fps).astype(int)
            self.width = int(self.capture.get(self.WIDTH))
            self.height = int(self.capture.get(self.HEIGHT))
        else:
            self.close()

    def isOpened(self):
        return self.capture is not None

    def close(self):
        self.capture.release()
        self.capture = None

    def seek(self, frame):
        self.capture.set(self.SEEK, frame)

    @pyqtSlot()
    def emit(self):
        if not self.running:
            self.close()
            return
        if self.rewinding:
            self.seek(0)
            self.rewinding = False
        if self.emitting:
            ready, self.frame = self.capture.read()
            if ready:
                if self.frame.ndim == 3:
                    self.frame = cv2.cvtColor(self.frame, self.BRG2RGB)
                self.newFrame.emit(self.frame)
            else:
                self.emitting = False
        QTimer.singleShot(self.delay, self.emit)

    @pyqtSlot()
    def start(self):
        if self.running:
            return
        self.running = True
        self.emitting = True
        self.rewinding = False
        self.emit()

    @pyqtSlot()
    def stop(self):
        self.running = False

    @pyqtSlot()
    def rewind(self):
        self.rewinding = True

    @pyqtSlot(bool)
    def pause(self, paused):
        self.emitting = not paused

    def isPaused(self):
        return not self.emitting

    @pyqtProperty(QSize)
    def size(self):
        return QSize(self.width, self.height)

    @pyqtProperty(int)
    def length(self):
        return int(self.capture.get(self.LENGTH))

    @pyqtProperty(int)
    def fps(self):
        return int(self.capture.get(self.FPS))

    @pyqtProperty(QRectF)
    def roi(self):
        return QRectF(0., 0., self.width, self.height)


if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    fn = '/Users/grier/data/fabdvr.avi'
    a = QVideoPlayer(fn)
    a.start()
    sys.exit(app.exec_())
