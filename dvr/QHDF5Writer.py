'''HDF5 video writer with per-frame timestamps.'''
from QVideo.lib import QVideoWriter
from QVideo.lib.videotypes import Image, FrameInfo
try:
    import h5py
except (ImportError, ModuleNotFoundError):
    h5py = None
from time import perf_counter
import logging


__all__ = ['QHDF5Writer']


logger = logging.getLogger(__name__)


class QHDF5Writer(QVideoWriter):

    '''Video writer for HDF5 files.

    Writes frames to an HDF5 file as a group of timestamped datasets.
    Each frame is stored under a key equal to its elapsed time in
    seconds since recording began.  A ``Timestamp`` attribute on the
    file records the absolute start time (UNIX epoch).

    The file is created on the first frame and closed explicitly by
    :meth:`close`.  If the file cannot be created, :meth:`open`
    returns ``False`` and no data are written.

    Parameters
    ----------
    filename : str
        Path to the output HDF5 file.
    *args :
        Forwarded to :class:`~QVideo.lib.QVideoWriter`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QVideoWriter`.
    '''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._file = None
        self._writer = None
        self._t0 = None

    def open(self, frame: Image) -> bool:
        '''Open the HDF5 file for writing.

        Called automatically by :meth:`~QVideo.lib.QVideoWriter.write`
        on the first frame.

        Parameters
        ----------
        frame : Image
            The first video frame (used only to trigger file creation;
            dimensions are not required in advance for HDF5).

        Returns
        -------
        bool
            ``True`` if the file was opened successfully; ``False`` if
            the file could not be created.
        '''
        try:
            self._file = h5py.File(self.filename, 'w',
                                   libver='latest',
                                   track_order=True)
        except OSError:
            logger.warning(f'Could not open {self.filename!r} for writing')
            return False
        self._t0 = None
        self._writer = self._file.create_group('images')
        return True

    def isOpen(self) -> bool:
        '''Return ``True`` if the HDF5 file is currently open.'''
        return self._file is not None and bool(self._file)

    def _write(self, frame: Image, info: FrameInfo | None = None) -> None:
        '''Write *frame* as a dataset keyed by elapsed capture time.

        The key is the time in seconds between the capture of the first
        recorded frame and the capture of this frame, so it is
        unaffected by delays between capture and writing.  The
        ``Timestamp`` file attribute is the UNIX time at which the first
        recorded frame was captured.
        '''
        if info is None:
            info = FrameInfo(0, perf_counter())
        if self._t0 is None:
            self._t0 = info.timestamp
            self._file.attrs['Timestamp'] = info.wallclock
        elapsed = info.timestamp - self._t0
        self._writer.create_dataset(f'{elapsed:.9f}', data=frame)

    def close(self) -> None:
        '''Close the HDF5 file and reset internal state.'''
        if self.isOpen():
            self._file.close()
        self._file = None
        self._writer = None
        self._t0 = None
