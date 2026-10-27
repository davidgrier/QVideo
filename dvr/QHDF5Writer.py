'''HDF5 video writer with per-frame timestamps.'''
import numpy as np
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


__all__ = ['QHDF5Writer', 'FORMAT_VERSION']


logger = logging.getLogger(__name__)

#: Version of the layout of the files that :class:`QHDF5Writer` makes.
#: Version 1 had one dataset for each frame in a group named ``images``.
FORMAT_VERSION = 2
#: How often the writer makes the frames that it has written safe [s].
_FLUSH_INTERVAL = 1.


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

    The file holds one dataset of frames and one array of metadata for each
    frame, in the order that the frames were captured:

    ``frames``
        The frames, as an array of shape ``(N, height, width)``, or
        ``(N, height, width, 3)`` for color.  Each frame is one chunk.
    ``timestamp``
        The time at which each frame was captured [s], from the capture of
        the first frame, as 64-bit floats.
    ``index``
        The :attr:`~QVideo.lib.videotypes.FrameInfo.index` of each frame,
        which skips the frames that the source delivered but this file does
        not hold.
    ``hardware_timestamp``
        The camera's own timestamp for each frame [s], or NaN if the camera
        gives none.

    The attributes of the file are ``format_version`` (2), ``Timestamp``
    (the UNIX time at which the first frame was captured) and ``fps`` (the
    frame rate that the writer was told).

    The file is written in the single-writer, multiple-reader mode of HDF5
    and flushed about once a second.  If the program dies, the file holds
    the frames up to the last flush, and opens with
    :class:`~QVideo.dvr.QHDF5Reader.QHDF5Reader` or ``h5py.File(name, 'r',
    swmr=True)``; another process can also read it while it is written.

    The file is created on the first frame, which gives the size and type of
    every frame that follows: a frame of another size or type ends the
    recording.  :meth:`close` finishes the file.  If the file cannot be
    created, :meth:`open` returns ``False`` and no data are written.

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
        self._frames = None
        self._columns: dict = {}
        self._t0 = None
        self._flushed = 0.

    def open(self, frame: Image) -> bool:
        '''Create the HDF5 file.

        Called automatically by :meth:`~QVideo.lib.QVideoWriter.write`
        on the first frame.  The datasets are made with the first frame
        that is written, because the single-writer mode does not let a file
        gain datasets.

        Parameters
        ----------
        frame : Image
            The first video frame (not used here).

        Returns
        -------
        bool
            ``True`` if the file was created; ``False`` if it could not be.
        '''
        try:
            self._file = h5py.File(self.filename, 'w', libver='latest')
        except OSError:
            logger.warning(f'Could not open {self.filename!r} for writing')
            return False
        return True

    def isOpen(self) -> bool:
        '''Return ``True`` if the HDF5 file is currently open.'''
        return self._file is not None and bool(self._file)

    def _create(self, frame: Image, info: FrameInfo) -> None:
        '''Make the datasets for frames like *frame* and begin to share.'''
        shape = frame.shape
        attrs = self._file.attrs
        attrs['format_version'] = FORMAT_VERSION
        attrs['Timestamp'] = info.wallclock
        attrs['fps'] = self.fps / self.nskip
        self._frames = self._file.create_dataset(
            'frames', (0,) + shape, maxshape=(None,) + shape,
            chunks=(1,) + shape, dtype=frame.dtype, **self._filter)
        for name, dtype in (('timestamp', 'f8'), ('index', 'i8'),
                            ('hardware_timestamp', 'f8')):
            self._columns[name] = self._file.create_dataset(
                name, (0,), maxshape=(None,), chunks=(1024,), dtype=dtype)
        self._file.swmr_mode = True
        self._t0 = info.timestamp
        self._flushed = perf_counter()

    def _write(self, frame: Image, info: FrameInfo | None = None) -> None:
        '''Append *frame* and its capture metadata to the datasets.

        The time of a frame is the time between the capture of the first
        recorded frame and the capture of this one, so it is unaffected
        by delays between capture and writing.
        '''
        if info is None:
            info = FrameInfo(0, perf_counter())
        if self._frames is None:
            self._create(frame, info)
        elif (frame.shape, frame.dtype) != (self._frames.shape[1:],
                                            self._frames.dtype):
            logger.warning(
                f'Frame of shape {frame.shape} and type {frame.dtype} does '
                f'not match the file, {self._frames.shape[1:]} and '
                f'{self._frames.dtype}: stopping recording')
            self.finished.emit()
            return
        n = len(self._frames)
        self._frames.resize(n + 1, axis=0)
        self._frames[n] = frame
        hardware = info.hardware_timestamp
        row = (info.timestamp - self._t0, info.index,
               np.nan if hardware is None else hardware)
        for dataset, value in zip(self._columns.values(), row):
            dataset.resize(n + 1, axis=0)
            dataset[n] = value
        if perf_counter() - self._flushed >= _FLUSH_INTERVAL:
            self._flush()

    def _flush(self) -> None:
        '''Write the datasets to the file, so that a crash spares them.'''
        for dataset in (self._frames, *self._columns.values()):
            dataset.flush()
        self._flushed = perf_counter()

    def close(self) -> None:
        '''Close the HDF5 file and reset internal state.'''
        if self.isOpen():
            self._file.close()
        self._file = None
        self._frames = None
        self._columns = {}
        self._t0 = None
