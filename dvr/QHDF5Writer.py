'''HDF5 video writer with per-frame timestamps.'''
from QVideo.lib import QVideoWriter
from QVideo.lib.videotypes import Image, FrameInfo
try:
    import h5py
except (ImportError, ModuleNotFoundError):
    h5py = None
try:
    import hdf5plugin
except (ImportError, ModuleNotFoundError):
    hdf5plugin = None
from time import perf_counter
import logging


__all__ = ['QHDF5Writer']


logger = logging.getLogger(__name__)


def _filter(name: str | None) -> dict:
    '''Return the keywords with which h5py applies the lossless filter *name*.

    ``'lzf'`` and ``'gzip'`` come with h5py; ``'zstd'``, ``'lz4'`` and
    ``'blosc2'`` need the ``hdf5plugin`` package, and no filter is used
    without it.
    '''
    if name in (None, 'lzf'):
        return {'compression': name} if name else {}
    if name == 'gzip':
        return {'compression': 'gzip', 'compression_opts': 1}
    if hdf5plugin is None:
        logger.info(f'hdf5plugin is not installed: not compressing ({name})')
        return {}
    return dict({'zstd': hdf5plugin.Zstd(clevel=1),
                 'lz4': hdf5plugin.LZ4(),
                 'blosc2': hdf5plugin.Blosc2(
                     cname='zstd', clevel=1,
                     filters=hdf5plugin.Blosc2.BITSHUFFLE)}[name])


class QHDF5Writer(QVideoWriter):

    '''Video writer for HDF5 files.

    Writes frames to an HDF5 file as a group of timestamped datasets.
    Each frame is stored under a key equal to its elapsed time in
    seconds since recording began.  A ``Timestamp`` attribute on the
    file records the absolute start time (UNIX epoch).

    The file is created on the first frame and closed explicitly by
    :meth:`close`.  If the file cannot be created, :meth:`open`
    returns ``False`` and no data are written.

    The frames are compressed without loss, so that every pixel, of any
    bit depth, is read back as it was written.  The default, Zstandard,
    runs several times faster than a camera needs and shrinks the file a
    little or a lot, depending on the image; reading such a file needs the
    ``hdf5plugin`` package.

    Parameters
    ----------
    filename : str
        Path to the output HDF5 file.
    compression : str or None
        The lossless filter for the frames: ``'zstd'``, ``'lz4'`` or
        ``'blosc2'`` (bit-shuffled Zstandard, best for 16-bit data), which
        need ``hdf5plugin`` and are skipped without it, ``'lzf'`` or
        ``'gzip'``, which come with h5py but are slow for large frames, or
        ``None`` for none.  Default: ``'zstd'``.
    *args :
        Forwarded to :class:`~QVideo.lib.QVideoWriter`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QVideoWriter`.
    '''

    def __init__(self, *args,
                 compression: str | None = 'zstd',
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._filter = _filter(compression)
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
        self._writer.create_dataset(
            f'{elapsed:.9f}', data=frame,
            chunks=frame.shape if self._filter else None, **self._filter)

    def close(self) -> None:
        '''Close the HDF5 file and reset internal state.'''
        if self.isOpen():
            self._file.close()
        self._file = None
        self._writer = None
        self._t0 = None
