'''Digital video recorder (DVR) subsystem.

Provides a composite widget and file I/O classes for recording and
playing back video streams captured from a
:class:`~QVideo.lib.QVideoSource.QVideoSource`.

Supported formats:

- **AVI, MKV, MP4** — via :class:`QOpenCVWriter` / :class:`QOpenCVReader`
- **HDF5** (``.h5``) — via :class:`QHDF5Writer` / :class:`QHDF5Reader`
  (requires ``h5py``)

Classes
-------
QDVRWidget
    Composite widget with record, play, pause, stop, and rewind controls.
QCircularBuffer
    Ring buffer that accumulates timestamped frames for later saving.
QCircularDVRWidget
    Widget for saving the last N seconds of video to disk on demand.
QOpenCVWriter
    OpenCV-backed writer for AVI, MKV, and MP4 files.
QOpenCVReader
    OpenCV-backed reader for common video file formats.
QOpenCVSource
    Threaded playback source backed by :class:`QOpenCVReader`.
QHDF5Writer
    HDF5-backed writer with per-frame timestamps (requires ``h5py``).
QHDF5Reader
    HDF5-backed reader for files written by :class:`QHDF5Writer`.
QHDF5Source
    Threaded playback source backed by :class:`QHDF5Reader`.
'''
from .QDVRWidget import QDVRWidget
from .QCircularBuffer import QCircularBuffer
from .QCircularDVRWidget import QCircularDVRWidget
from .QOpenCVWriter import QOpenCVWriter
from .QOpenCVReader import QOpenCVReader, QOpenCVSource
from .QHDF5Writer import QHDF5Writer
from .QHDF5Reader import QHDF5Reader, QHDF5Source

__all__ = [
    'QDVRWidget',
    'QCircularBuffer',
    'QCircularDVRWidget',
    'QOpenCVWriter',
    'QOpenCVReader', 'QOpenCVSource',
]

try:
    import h5py as _h5py
    __all__ += ['QHDF5Writer', 'QHDF5Reader', 'QHDF5Source']
except (ImportError, ModuleNotFoundError):
    pass
