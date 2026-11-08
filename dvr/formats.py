'''The video file formats that can be recorded and played.

Two tables map a file extension to the class that writes it
(:class:`~QVideo.lib.QVideoWriter.QVideoWriter`) or reads it
(:class:`~QVideo.lib.QVideoReader.QVideoReader`).  PyAV handles ``.avi``,
``.mkv`` and ``.mp4`` if it is installed, and OpenCV if not; ``.h5`` needs
``h5py``.  Both the recorder and the player look their classes up here, as do
the widgets, so an entry that is changed or added applies to all of them::

    from QVideo.dvr import formats
    formats.Writer['.mkv'] = QOpenCVWriter
'''
import importlib.util
from pathlib import Path
from QVideo.lib import QVideoReader, QVideoWriter
from .QOpenCVWriter import QOpenCVWriter
from .QOpenCVReader import QOpenCVReader
from .QPyAVWriter import QPyAVWriter
from .QPyAVReader import QPyAVReader
from .QHDF5Writer import QHDF5Writer
from .QHDF5Reader import QHDF5Reader


__all__ = ['Writer', 'Reader', 'Groups', 'writerClass', 'readerClass',
           'openWriter', 'openVideo', 'fileFilter']

#: Whether PyAV is installed.
pyav_available = importlib.util.find_spec('av') is not None
#: Whether h5py is installed.
h5py_available = importlib.util.find_spec('h5py') is not None

#: The class that writes the files with each extension.
Writer: dict[str, type] = dict.fromkeys(
    ('.avi', '.mkv', '.mp4'), QPyAVWriter if pyav_available
    else QOpenCVWriter)
#: The class that reads the files with each extension.
Reader: dict[str, type] = dict.fromkeys(
    ('.avi', '.mkv', '.mp4'), QPyAVReader if pyav_available
    else QOpenCVReader)
#: The extensions that the file dialog lists together, by label.
Groups: dict[str, set[str]] = {
    'Lossless Video': {'.avi', '.mkv'},
    'Video': {'.mp4'}}

if h5py_available:
    Writer['.h5'] = QHDF5Writer
    Reader['.h5'] = QHDF5Reader
    Groups['HDF5 files'] = {'.h5'}


def _lookup(table: dict[str, type], filename: str) -> type:
    suffix = Path(filename).suffix.lower()
    if suffix not in table:
        raise ValueError(f'Unsupported file format {suffix!r}: '
                         f'use one of {", ".join(sorted(table))}')
    return table[suffix]


def writerClass(filename: str) -> type:
    '''Return the class that writes files like *filename*.

    Raises
    ------
    ValueError
        If the extension of *filename* is not in :data:`Writer`.
    '''
    return _lookup(Writer, filename)


def openWriter(filename: str,
               fps: float,
               nframes: int = 10_000,
               nskip: int = 1,
               overwrite: bool = False) -> QVideoWriter:
    '''Return a writer for *filename*, to which frames are written.

    The one place that checks a recording before it starts: the extension
    chooses the class (:data:`Writer`), and an existing file is an error
    unless *overwrite* is given, so that a recording cannot destroy
    another.

    Parameters
    ----------
    filename : str
        The file to write.
    fps : float
        The frame rate that the file declares.
    nframes : int
        The number of frames to write; the writer then finishes.
    nskip : int
        Write every *nskip*-th frame.
    overwrite : bool
        Replace *filename* if it exists.

    Raises
    ------
    ValueError
        If the extension of *filename* is not in :data:`Writer`.
    FileExistsError
        If *filename* exists and *overwrite* is ``False``.
    '''
    writer_class = writerClass(filename)
    if not overwrite and Path(filename).exists():
        raise FileExistsError(
            f'{filename!r} exists; use overwrite=True to replace it')
    return writer_class(filename, fps=fps, nframes=nframes, nskip=nskip)


def readerClass(filename: str) -> type:
    '''Return the class that reads files like *filename*.

    Raises
    ------
    ValueError
        If the extension of *filename* is not in :data:`Reader`.
    '''
    return _lookup(Reader, filename)


def openVideo(filename: str) -> QVideoReader:
    '''Open a video file for reading, whatever its format.

    The reader can be used without a Qt application and without a thread:
    ``len(video)``, ``video[i]``, ``video[a:b]`` and iteration give the
    frames as arrays.

    Raises
    ------
    ValueError
        If the extension of *filename* is not in :data:`Reader`.
    OSError
        If the file cannot be opened.
    '''
    reader = readerClass(filename)(filename)
    if not reader.isOpen():
        raise OSError(f'cannot open {filename!r} for reading')
    return reader


def fileFilter(save: bool) -> str:
    '''Return a file-dialog filter for the formats that can be handled.

    Parameters
    ----------
    save : bool
        If ``True``, list the extensions of :data:`Writer`; otherwise
        those of :data:`Reader`.

    Returns
    -------
    str
        A ``;;``-separated filter string suitable for ``QFileDialog``,
        with the extensions grouped by :data:`Groups`.
    '''
    formats = set(Writer if save else Reader)
    parts = []
    covered = set()
    for label, exts in Groups.items():
        matching = sorted(exts & formats)
        if matching:
            covered |= set(matching)
            parts.append(f'{label} ({" ".join("*" + e for e in matching)})')
    ungrouped = sorted(formats - covered)
    if ungrouped:
        parts.append(
            f'Other files ({" ".join("*" + e for e in ungrouped)})')
    return ';;'.join(parts) if parts else 'All files (*)'
