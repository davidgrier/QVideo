'''Ring buffer that accumulates timestamped frames for later saving.'''
from collections import deque
from pathlib import Path
from time import time
from qtpy import QtCore
import numpy as np
import logging

from QVideo.lib.videotypes import Image
from .QOpenCVWriter import QOpenCVWriter


__all__ = ['QCircularBuffer']


logger = logging.getLogger(__name__)


class QCircularBuffer(QtCore.QObject):

    '''Ring buffer that accumulates timestamped frames for later saving.

    Each frame appended via :meth:`append` is stored together with a
    wall-clock timestamp.  When the buffer is full the oldest frame is
    discarded.  :meth:`save` writes the current contents to disk in one
    batch, using the stored timestamps to reproduce accurate timing.

    For OpenCV formats (``.avi``, ``.mkv``, ``.mp4``) the frame rate is
    computed from the elapsed time between the first and last stored
    timestamp, so playback speed reflects actual capture speed rather
    than a nominal rate.

    For HDF5 (``.h5``) each frame is stored as a dataset keyed by its
    elapsed time in seconds from the first frame, matching the layout
    produced by :class:`~QVideo.dvr.QHDF5Writer.QHDF5Writer`.

    Parameters
    ----------
    fps : float
        Nominal frame rate used to size the buffer and as a fallback
        fps when fewer than two frames have been captured.
    duration : int
        Buffer length in seconds.  The buffer holds at most
        ``fps × duration`` frames.

    Slots
    -----
    append(frame : numpy.ndarray) -> None
        Add *frame* to the buffer with the current wall-clock time.
    '''

    def __init__(self,
                 fps: float = 24.,
                 duration: int = 5,
                 parent=None) -> None:
        super().__init__(parent)
        self._fps = float(fps)
        self._duration = max(1, int(duration))
        self._buffer: deque = deque(maxlen=max(1, int(self._fps * self._duration)))

    @property
    def fps(self) -> float:
        '''Nominal frame rate [frames per second].'''
        return self._fps

    @fps.setter
    def fps(self, fps: float) -> None:
        self._fps = float(fps)
        self._resize()

    @property
    def duration(self) -> int:
        '''Buffer length [seconds].'''
        return self._duration

    @duration.setter
    def duration(self, seconds: int) -> None:
        self._duration = max(1, int(seconds))
        self._resize()

    def _resize(self) -> None:
        maxlen = max(1, int(self._fps * self._duration))
        items = list(self._buffer)
        self._buffer = deque(items[-maxlen:], maxlen=maxlen)

    def __len__(self) -> int:
        return len(self._buffer)

    def clear(self) -> None:
        '''Discard all buffered frames.'''
        self._buffer.clear()

    @QtCore.Slot(np.ndarray)
    def append(self, frame: Image) -> None:
        '''Add *frame* to the buffer with the current wall-clock timestamp.

        Parameters
        ----------
        frame : numpy.ndarray
            Video frame to buffer.
        '''
        self._buffer.append((time(), frame))

    def save(self, filename: str) -> bool:
        '''Write buffered frames to *filename*.

        The file format is determined by the extension.  HDF5 (``.h5``)
        preserves per-frame timestamps; OpenCV formats use a frame rate
        computed from the elapsed time between the first and last frame.

        Parameters
        ----------
        filename : str
            Output file path.

        Returns
        -------
        bool
            ``True`` on success, ``False`` if the buffer is empty or
            the file could not be written.
        '''
        if not self._buffer:
            return False
        items = list(self._buffer)
        suffix = Path(filename).suffix
        if suffix == '.h5':
            return self._saveHDF5(filename, items)
        return self._saveOpenCV(filename, items)

    def _actualFps(self, items: list) -> float:
        if len(items) < 2:
            return self._fps
        elapsed = items[-1][0] - items[0][0]
        return (len(items) - 1) / elapsed if elapsed > 0 else self._fps

    def _saveHDF5(self, filename: str, items: list) -> bool:
        try:
            import h5py
        except ImportError:
            logger.error('h5py is required to save HDF5 files')
            return False
        t0 = items[0][0]
        try:
            with h5py.File(filename, 'w', libver='latest',
                           track_order=True) as f:
                f.attrs['Timestamp'] = t0
                grp = f.create_group('images')
                for t, frame in items:
                    grp.create_dataset(f'{t - t0:.9f}', data=frame)
        except OSError:
            logger.warning(f'Could not write {filename!r}')
            return False
        return True

    def _saveOpenCV(self, filename: str, items: list) -> bool:
        fps = self._actualFps(items)
        frames = [frame for _, frame in items]
        writer = QOpenCVWriter(filename, fps=fps,
                               nframes=len(frames), nskip=1)
        if not writer.open(frames[0]):
            logger.warning(f'Could not open {filename!r} for writing')
            return False
        for frame in frames:
            writer._write(frame)
        writer.close()
        return True
