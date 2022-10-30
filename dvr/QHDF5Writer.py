# -*- coding: utf-8 -*-

from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot)
import numpy as np
import h5py
import time

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QHDF5Writer(QObject):
    '''Class for saving H5 video files

    Inherits
    --------
    PyQt5.QtCore.QObject
    '''

    frameNumber = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self,
                 filename: str,
                 nframes: int = 10000,
                 nskip: int = 1):
        super(QHDF5Writer, self).__init__()
        # h5py.get_config().track_order = True
        self.file = h5py.File(filename, 'w', libver='latest',
                              track_order=True)
        self.video = self.file.create_group('images')
        self.start = time.time()
        self.file.attrs.update({'Timestamp': self.start})
        self.framenumber = 0
        self.nskip = nskip
        self.target = nframes

    @pyqtSlot(np.ndarray)
    def write(self, frame: np.ndarray) -> None:
        '''Writes video frame to video file

        Arguments
        ---------
        frame: numpy.ndarray
            Video deata to write
        '''
        if (self.framenumber >= self.target):
            self.finished.emit()
            return
        now = time.time() - self.start
        if self.framenumber % self.nskip == 0:
            self.video.create_dataset(str(now), data=frame)
        self.framenumber += 1
        self.frameNumber.emit(self.framenumber)

    @pyqtSlot()
    def close(self) -> None:
        '''Closes video file'''
        self.file.close()
