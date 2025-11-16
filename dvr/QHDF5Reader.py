from QVideo.lib import (QVideoReader, QVideoSource)
from pyqtgraph.Qt.QtCore import (pyqtSlot, pyqtProperty)
import h5py


__all__ = ['QHDF5Reader', 'QHDF5Source']


class QHDF5Reader(QVideoReader):

    '''Video reader for HDF5 files

    Reads frames from an HDF5 file containing image datasets.

    Inherits
    --------
    QVideo.lib.QVideoReader

    Parameters
    ----------
    filename : str
        Path to the HDF5 file to read.
    '''

    def _initialize(self) -> bool:
        if (file := h5py.File(self.filename, 'r')) is None:
            return False
        self.file = file
        self.images = self.file['images']
        self.keys = list(self.images.keys())
        self._length = len(self.keys)
        self._framenumber = 0
        self._width, self._height = self.images[self.keys[0]][()].shape[0:2]
        return True

    def _deinitialize(self) -> None:
        self.file.close()

    def read(self) -> QVideoReader.CameraData:
        if self._framenumber >= len(self.keys):
            return False, None
        key = self.keys[self._framenumber]
        self.frame = self.images[key][()]
        self._framenumber += 1
        return True, self.frame

    @pyqtSlot(int)
    def seek(self, framenumber: int) -> None:
        '''Advamces playback to specified frame number'''
        self._framenumber = framenumber
        self.now = self.timestamp()

    @pyqtProperty(float)
    def fps(self) -> float:
        return 30.

    @pyqtProperty(int)
    def length(self) -> int:
        return self._length

    @pyqtProperty(int)
    def framenumber(self) -> int:
        return self._framenumber

    @pyqtProperty(int)
    def width(self) -> int:
        return self._width

    @pyqtProperty(int)
    def height(self) -> int:
        return self._height


class QHDF5Source(QVideoSource):

    '''Video source for HDF5 files

    Inherits
    --------
    QVideo.lib.QVideoSource

    Parameters
    ----------
    reader : str | QHDF5Reader
        Path to the HDF5 file to read or an instance of QHDF5Reader.
    '''

    def __init__(self, reader: str | QHDF5Reader) -> None:
        if isinstance(reader, str):
            reader = QHDF5Reader(reader)
        super().__init__(reader)
