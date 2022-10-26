# -*- coding: utf-8 -*-

from PyQt5.QtCore import (QObject, QTimer, pyqtSignal, pyqtSlot)
import h5py
import numpy as np


class QHDF5Player(QObject):

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, filename=None):
        super(QHDF5Player, self).__init__()

        self.running = False

        self.file = h5py.File(filename, 'r')
        self.images = self.file['images']
        self.keys = list(self.images.keys())
        self.nframes = len(self.keys)
        self.framenumber = 0
        self.now = self.timestamp()

    def isOpened(self):
        return self.file is not None

    def close(self):
        self.file.close()

    def timestamp(self):
        return float(self.keys[self.framenumber])

    def seek(self, framenumber):
        self.framenumber = framenumber
        self.now = self.timestamp()

    @pyqtSlot()
    def emit(self):
        if not self.running:
            self.close()
            return
        delay = 10.
        if self.rewinding:
            self.seek(0)
            self.rewinding = False
        if self.emitting:
            key = self.keys[self.framenumber]
            self.frame = self.images[key][()]
            self.newFrame.emit(self.frame)
            now = float(key)
            delay = np.round(1000.*(now - self.now)).astype(int)
            self.framenumber += 1
            if self.framenumber >= self.nframes:
                self.emitting = False
            else:
                self.now = now
        QTimer.singleShot(delay, self.emit)

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
