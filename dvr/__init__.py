'''Digital video recorder (DVR) subsystem.

Provides a composite widget and file I/O classes for recording and
playing back video streams captured from a
:class:`~QVideo.lib.QVideoSource.QVideoSource`.

Supported formats:

- **AVI, MKV, MP4** — via :class:`QPyAVWriter` / :class:`QPyAVReader` if
  PyAV is installed, otherwise via :class:`QOpenCVWriter` /
  :class:`QOpenCVReader`
- **HDF5** (``.h5``) — via :class:`QHDF5Writer` / :class:`QHDF5Reader`
  (requires ``h5py``)

Classes
-------
QDVRWidget
    Composite widget with record, play, pause, stop, and rewind controls.
QBacklogMonitor
    Measures how far the writer of a recording is behind the camera.
QSourceSelector
    Radio buttons that choose which stream to record.
QRecorder
    Records the frames of a source to a file, without a window.
QPlayer
    Plays a video file at its own frame rate, without a window.
QCircularBuffer
    Ring buffer that keeps the most recent frames and their capture times.
QCircularDVRWidget
    Widget for saving the last N seconds of video to disk on demand.
QOpenCVWriter
    OpenCV-backed writer for AVI, MKV, and MP4 files.
QOpenCVReader
    OpenCV-backed reader for common video file formats.
QPyAVWriter
    PyAV-backed writer for AVI, MKV, and MP4 files (requires ``av``).
QPyAVReader
    PyAV-backed reader for common video file formats (requires ``av``).
QHDF5Writer
    HDF5-backed writer with per-frame timestamps (requires ``h5py``).
QHDF5Reader
    HDF5-backed reader for files written by :class:`QHDF5Writer`.
'''
from .QDVRWidget import QDVRWidget
from .QBacklogMonitor import QBacklogMonitor
from .QSourceSelector import QSourceSelector
from .QRecorder import QRecorder
from .QPlayer import QPlayer
from .QCircularBuffer import QCircularBuffer
from .QCircularDVRWidget import QCircularDVRWidget
from .QOpenCVWriter import QOpenCVWriter
from .QOpenCVReader import QOpenCVReader
from .QPyAVWriter import QPyAVWriter
from .QPyAVReader import QPyAVReader
from .QHDF5Writer import QHDF5Writer
from .QHDF5Reader import QHDF5Reader

__all__ = [
    'QDVRWidget',
    'QBacklogMonitor',
    'QSourceSelector',
    'QRecorder',
    'QPlayer',
    'QCircularBuffer',
    'QCircularDVRWidget',
    'QOpenCVWriter',
    'QOpenCVReader',
    'QPyAVWriter', 'QPyAVReader',
]

try:
    import h5py as _h5py
    __all__ += ['QHDF5Writer', 'QHDF5Reader']
except (ImportError, ModuleNotFoundError):
    pass
