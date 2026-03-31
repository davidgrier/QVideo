from qtpy import QtCore
from QVideo.lib import QVideoReader, QVideoSource
from pathlib import Path
import h5py


__all__ = ['QHDF5Reader', 'QHDF5Source']


class QHDF5Reader(QVideoReader):

    '''Video reader for HDF5 files.

    Reads frames from an HDF5 file containing an ``images`` group of
    timestamped datasets, as written by :class:`QHDF5Writer`.

    Parameters
    ----------
    filename : str
        Path to the HDF5 file to read.
    '''

    def _initialize(self) -> bool:
        try:
            self.file = h5py.File(self.filename, 'r')
            self.images = self.file['images']
        except (OSError, KeyError):
            return False
        self.keys = sorted(self.images.keys(), key=float)
        self._length = len(self.keys)
        if not self.keys:
            return False
        self._framenumber = 0
        self._height, self._width = self.images[self.keys[0]][()].shape[0:2]
        return True

    def _deinitialize(self) -> None:
        self.file.close()

    def read(self) -> QVideoReader.CameraData:
        if self._framenumber >= len(self.keys):
            return False, None
        key = self.keys[self._framenumber]
        frame = self.images[key][()]
        self._framenumber += 1
        return True, frame

    @QtCore.Slot(int)
    def seek(self, framenumber: int) -> None:
        '''Advance playback to specified frame number.'''
        self._framenumber = framenumber

    @QtCore.Property(float)
    def fps(self) -> float:
        if len(self.keys) < 2:
            return 30.
        elapsed = float(self.keys[-1]) - float(self.keys[0])
        if elapsed <= 0.:
            return 30.
        return (len(self.keys) - 1) / elapsed

    @QtCore.Property(int)
    def length(self) -> int:
        return self._length

    @QtCore.Property(int)
    def framenumber(self) -> int:
        return self._framenumber

    @QtCore.Property(int)
    def width(self) -> int:
        return self._width

    @QtCore.Property(int)
    def height(self) -> int:
        return self._height


class QHDF5Source(QVideoSource):

    '''Video source for HDF5 files.

    Parameters
    ----------
    reader : str, Path, or QHDF5Reader
        Path to the HDF5 file to read, or an existing
        :class:`QHDF5Reader` instance.
    '''

    def __init__(self, reader: str | Path | QHDF5Reader) -> None:
        if isinstance(reader, (str, Path)):
            reader = QHDF5Reader(str(reader))
        super().__init__(reader)
