'''HDF5 video reader and threaded playback source.'''
from qtpy import QtCore
from QVideo.lib import QCamera, QVideoReader, QVideoSource
from pathlib import Path
try:
    import h5py
except (ImportError, ModuleNotFoundError):
    h5py = None


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
            self._file = h5py.File(self.filename, 'r')
            self._images = self._file['images']
        except (OSError, KeyError):
            return False
        self._keys = sorted(self._images.keys(), key=float)
        self._length = len(self._keys)
        if not self._keys:
            return False
        self._framenumber = 0
        self._height, self._width = (
            self._images[self._keys[0]][()].shape[0:2])
        return True

    def _deinitialize(self) -> None:
        self._file.close()

    def read(self) -> QCamera.CameraData:
        '''Read the next frame from the HDF5 file.

        Returns
        -------
        tuple[bool, ndarray or None]
            ``(True, frame)`` on success, ``(False, None)`` when past
            the end.
        '''
        if self._framenumber >= len(self._keys):
            return False, None
        key = self._keys[self._framenumber]
        frame = self._images[key][()]
        self._framenumber += 1
        return True, frame

    @QtCore.Slot(int)
    def seek(self, framenumber: int) -> None:
        '''Advance playback to specified frame number.'''
        self._framenumber = framenumber

    @property
    def fps(self) -> float:
        '''Estimated frame rate derived from the recorded timestamps [fps].

        Computed as ``(n_frames - 1) / total_duration``.  Falls back to
        30 fps when fewer than two frames are present or the timestamps
        span zero time.
        '''
        if len(self._keys) < 2:
            return 30.
        elapsed = float(self._keys[-1]) - float(self._keys[0])
        if elapsed <= 0.:
            return 30.
        return (len(self._keys) - 1) / elapsed

    @property
    def length(self) -> int:
        '''Total number of frames in the HDF5 file.'''
        return self._length

    @property
    def framenumber(self) -> int:
        '''Index of the next frame to be returned by :meth:`read`.'''
        return self._framenumber

    @property
    def width(self) -> int:
        '''Frame width in pixels.'''
        return self._width

    @property
    def height(self) -> int:
        '''Frame height in pixels.'''
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
