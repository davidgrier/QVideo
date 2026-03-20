'''Abstract base class for video file readers.'''
from abc import ABCMeta, abstractmethod
from pyqtgraph.Qt import QtCore
from QVideo.lib import QCamera
import QVideo
from pathlib import Path
import logging


logger = logging.getLogger(__name__)

__all__ = ['QVideoReader']


class QVideoReaderMeta(type(QtCore.QObject), ABCMeta):
    pass


class QVideoReader(QtCore.QObject, metaclass=QVideoReaderMeta):

    '''Abstract base class for video-file readers.

    Provides a unified interface for reading frames from a video file,
    including rate-limited frame delivery and random access via :meth:`seek`.
    Pause/resume control is the responsibility of the enclosing
    :class:`~QVideo.lib.QVideoSource`.

    Subclasses implement :meth:`_initialize`, :meth:`_deinitialize`,
    :meth:`read`, and the abstract properties :attr:`fps`, :attr:`width`,
    :attr:`height`, :attr:`framenumber`, and :attr:`length`, as well as
    the :meth:`seek` method.

    Parameters
    ----------
    filename : str
        Path to the video file to open.

    Signals
    -------
    shapeChanged(QSize)
        Emitted when the file is opened and the frame dimensions are known.

    Type Aliases
    ------------
    CameraData : tuple[bool, Image | None]
        Return type of :meth:`read`, shared with :class:`~QVideo.lib.QCamera`.

    Notes
    -----
    :meth:`saferead` paces frame delivery by sleeping :attr:`delay`
    milliseconds between reads so that callers receive frames at
    approximately the correct playback rate.
    '''

    CameraData = QCamera.CameraData

    shapeChanged = QtCore.pyqtSignal(QtCore.QSize)

    def __init__(self, filename: str) -> None:
        '''Initialise and open the video reader.

        Parameters
        ----------
        filename : str
            Path to the video file.
        '''
        super().__init__()
        self.filename = filename
        self._isopen = False
        self.open()

    def __enter__(self) -> 'QVideoReader':
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @QtCore.pyqtSlot()
    def open(self) -> 'QVideoReader':
        '''Open the video file.

        Calls :meth:`_initialize` only if not already open.  Emits
        :attr:`shapeChanged` on success and logs a warning on failure.

        Returns
        -------
        QVideoReader
            ``self``, to allow chaining.
        '''
        if not self._isopen:
            self._isopen = bool(self._initialize())
            if self._isopen:
                self.shapeChanged.emit(self.shape)
            else:
                logger.warning(f'{type(self).__name__}: initialization failed')
        return self

    @QtCore.pyqtSlot()
    def close(self) -> None:
        '''Close the video file.

        Safe to call on an already-closed reader.
        '''
        if self._isopen:
            self._deinitialize()
        self._isopen = False

    def isOpen(self) -> bool:
        '''Return whether the file is currently open.'''
        return self._isopen

    @abstractmethod
    def _initialize(self) -> bool:
        '''Open the video file so that :meth:`read` will succeed.

        Returns
        -------
        bool
            ``True`` if the file was opened successfully.
        '''

    @abstractmethod
    def _deinitialize(self) -> None:
        '''Close the video file so that deletion or re-opening succeeds.'''

    @abstractmethod
    def read(self) -> CameraData:
        '''Read the next frame from the video file.

        Returns
        -------
        tuple[bool, ndarray or None]
            ``(True, frame)`` on success, ``(False, None)`` at end-of-file
            or on error.
        '''

    def saferead(self) -> CameraData:
        '''Read one frame, pacing delivery to the file's native frame rate.

        Blocks for :attr:`delay` milliseconds before each read so that
        callers receive frames at approximately the correct playback rate.

        Returns
        -------
        tuple[bool, ndarray or None]
            Result of :meth:`read`.
        '''
        QtCore.QThread.msleep(self.delay)
        return self.read()

    @property
    @abstractmethod
    def fps(self) -> float:
        '''Frame rate of the video file [frames per second].'''

    @property
    @abstractmethod
    def length(self) -> int:
        '''Total number of frames in the video file.'''

    @property
    @abstractmethod
    def framenumber(self) -> int:
        '''Current frame index (zero-based).'''

    @property
    @abstractmethod
    def width(self) -> int:
        '''Frame width in pixels.'''

    @property
    @abstractmethod
    def height(self) -> int:
        '''Frame height in pixels.'''

    @property
    def delay(self) -> int:
        '''Inter-frame delay in milliseconds, derived from :attr:`fps`.'''
        return int(1000. / self.fps)

    @property
    def shape(self) -> QtCore.QSize:
        '''Frame dimensions as ``QSize(width, height)``.'''
        return QtCore.QSize(int(self.width), int(self.height))

    @QtCore.pyqtSlot(int)
    @abstractmethod
    def seek(self, framenumber: int) -> None:
        '''Seek to the specified frame.

        Parameters
        ----------
        framenumber : int
            Target frame index (zero-based).
        '''

    @QtCore.pyqtSlot()
    def rewind(self) -> None:
        '''Seek to the first frame.'''
        self.seek(0)

    @staticmethod
    def examplevideo() -> str:  # pragma: no cover
        '''Return the path to the bundled example video file.'''
        path = Path(QVideo.__file__).parent / 'docs' / 'diatom3.avi'
        return str(path)

    @classmethod
    def example(cls: 'QVideoReader') -> None:  # pragma: no cover
        '''Print file metadata and read a few frames.'''
        filename = cls.examplevideo()
        video = cls(filename)
        print(filename)
        print(f'{video.length = } frames')
        print(f'{video.width = } pixels')
        print(f'{video.height = } pixels')
        print(f'{video.fps = } fps')
        video.close()
        with video:
            for _ in range(5):
                ok, frame = video.read()
                print(f'{video.framenumber} ', end='')
            print('done')
        with video:
            for _ in range(5):
                ok, frame = video.read()
                print(f'{video.framenumber} ', end='')
            print('done')
