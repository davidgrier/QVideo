# -*- coding: utf-8 -*-

from PyQt5.QtCore import (QObject, QTimer, pyqtSignal, pyqtSlot)
import h5py
import numpy as np
from typing import Optional


class QHDF5Player(QObject):
    '''Class for playing H5 video files

    Inherits
    --------
    PyQt5.QtCore.QObject
    '''

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self,
                 filename: Optional[str] = None) -> None:
        super(QHDF5Player, self).__init__()

        self.running = False

        self.file = h5py.File(filename, 'r')
        self.images = self.file['images']
        self.keys = list(self.images.keys())
        self.nframes = len(self.keys)
        self.framenumber = 0
        self.now = self.timestamp()

    def isOpened(self) -> bool:
        '''Returns True if playable file is open'''
        return self.file is not None

    def close(self) -> None:
        '''Closes video file'''
        self.file.close()

    def timestamp(self) -> float:
        '''Returns timestamp from current frame'''
        return float(self.keys[self.framenumber])

    def seek(self, framenumber: int) -> None:
        '''Advamces playback to specified frame number'''
        self.framenumber = framenumber
        self.now = self.timestamp()

    @pyqtSlot()
    def emit(self) -> None:
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
