'''HDF5 video reader and threaded playback source.'''
import numpy as np
from qtpy import QtCore
from QVideo.lib import QCamera, QVideoReader
from .QHDF5Writer import FORMAT_VERSION
import logging
try:
    import h5py
except (ImportError, ModuleNotFoundError):
    h5py = None
try:
    import hdf5plugin  # noqa: F401  registers the filters of the files
except (ImportError, ModuleNotFoundError):
    hdf5plugin = None


__all__ = ['QHDF5Reader']


logger = logging.getLogger(__name__)


class QHDF5Reader(QVideoReader):

    '''Video reader for HDF5 files.

    Reads the files that :class:`~QVideo.dvr.QHDF5Writer.QHDF5Writer`
    makes, including a file whose recording was cut short, and the files
    of version 1, which held each frame in a dataset of its own in a group
    named ``images``.

    Parameters
    ----------
    filename : str
        Path to the HDF5 file to read.
    '''

    def _initialize(self) -> bool:
        try:
            self._file = self._open()
        except OSError:
            return False
        version = self._file.attrs.get('format_version', 1)
        if version > FORMAT_VERSION:
            logger.warning(f'{self.filename!r} has format version {version}'
                           f', which this QVideo does not read')
            return self._fail()
        try:
            self._load()
        except KeyError:
            return self._fail()
        if not self._length:
            return self._fail()
        self._framenumber = 0
        try:
            self._height, self._width = self._frame(0).shape[0:2]
        except OSError:
            logger.warning(f'Cannot read {self.filename!r}: if it is '
                           'compressed, install the hdf5plugin package')
            return self._fail()
        return True

    def _open(self):
        '''Open the file, in the way that reads a file still being written.

        A file that the writer has not closed, because it is still writing
        or because the program stopped, opens only in the mode of a reader
        that shares the file with one writer.
        '''
        try:
            return h5py.File(self.filename, 'r', libver='latest', swmr=True)
        except OSError:
            return h5py.File(self.filename, 'r')

    def _load(self) -> None:
        '''Find the frames and the time of each one.'''
        if 'frames' in self._file:
            self._frames = self._file['frames']
            times = self._file['timestamp'][()]
            self._keys = None
            # A file that was cut short may hold a frame more than a time.
            self._length = min(len(self._frames), len(times))
            self._times = times[:self._length]
        else:
            self._images = self._file['images']
            self._keys = sorted(self._images.keys(), key=float)
            self._length = len(self._keys)
            self._times = np.array(self._keys, dtype=float)

    def _fail(self) -> bool:
        self._file.close()
        return False

    def _frame(self, framenumber: int) -> np.ndarray:
        if self._keys is None:
            return self._frames[framenumber]
        return self._images[self._keys[framenumber]][()]

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
        if self._framenumber >= self._length:
            return False, None
        frame = self._frame(self._framenumber)
        self._framenumber += 1
        return True, frame

    @QtCore.Slot(int)
    def seek(self, framenumber: int) -> None:
        '''Advance playback to specified frame number.'''
        self._framenumber = framenumber

    @property
    def timestamps(self) -> np.ndarray:
        '''Capture time of each frame [s], from the capture of the first.'''
        return self._times

    @property
    def fps(self) -> float:
        '''Frame rate derived from the recorded timestamps [fps].

        Computed as ``(n_frames - 1) / total_duration``.  Falls back to
        30 fps when fewer than two frames are present or the timestamps
        span zero time.
        '''
        if self._length < 2:
            return 30.
        elapsed = self._times[-1] - self._times[0]
        if elapsed <= 0.:
            return 30.
        return (self._length - 1) / elapsed

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
