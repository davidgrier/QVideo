# -*- coding: utf-8 -*-

from pyqtgraph.Qt.QtCore import pyqtSlot
from QVideo.lib import QVideoWriter
from QVideo.lib.types import Image
import h5py
from time import time


class QHDF5Writer(QVideoWriter):

    def open(self, frame: Image) -> bool:
        self.file = h5py.File(self.filename, 'w',
                              libver='latest',
                              track_order=True)
        self.start = time()
        self.file.attrs.update({'Timestamp': self.start})
        self._writer = self.file.create_group('images')
        return True

    def isOpen(self) -> bool:
        return hasattr(self, 'file') and bool(self.file)

    def _write(self, frame: Image) -> None:
        now = time() - self.start
        self._writer.create_dataset(str(now), data=frame)

    @pyqtSlot()
    def close(self) -> None:
        if self.isOpen():
            self.file.close()
