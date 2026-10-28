'''Abstract base class for video file writers.'''
from abc import abstractmethod
from qtpy import QtCore
from QVideo.lib._qabc import QABCMeta
from QVideo.lib.videotypes import Image, FrameInfo
from time import perf_counter
import numpy as np
import logging


logger = logging.getLogger(__name__)

__all__ = ['QVideoWriter']


class QVideoWriter(QtCore.QObject, metaclass=QABCMeta):
    '''Abstract base class for saving videos to files

    Parameters
    ----------
    filename : str
        The output video filename.
    fps : int
        The frame rate of the output video [frames per second].
    nframes : int
        The maximum number of frames to write.
    nskip : int
        Write every *nskip*-th frame received; 1 writes every frame.
        The file declares *fps* whatever *nskip* is, so a recording of
        a source at its own frame rate plays back *nskip* times
        faster than the scene happened (a time-lapse); HDF5 files
        also store each frame's capture time.
    kwargs : dict
        Additional keyword arguments to pass to the QObject constructor.

    Returns
    -------
    QVideoWriter : QObject
        The video writer object.

    Signals
    -------
    frameNumber(int)
        Emitted when a frame is written, providing the number of frames
        written so far.
    finished(str)
        Emitted once when the writer stops, with the reason: an empty
        string when it has the frames that it was asked for, otherwise an
        explanation.  A writer that has stopped ignores the frames that
        follow.

    Slots
    -----
    write(frame: Image, info: FrameInfo | None = None) -> None
        Write a video frame to the file.
    close() -> None
        Close the video file.
    shutdown() -> None
        Close the file and end the writer's thread, after the frames
        already waiting have been written.

    Properties
    ----------
    filename : str
        The output video filename.
    fps : int
        The frame rate of the output video [frames per second].
    nskip : int
        Write every *nskip*-th frame received; 1 writes every frame.
        The file declares *fps* whatever *nskip* is, so a recording of
        a source at its own frame rate plays back *nskip* times
        faster than the scene happened (a time-lapse); HDF5 files
        also store each frame's capture time.
    nframes : int
        The maximum number of frames to write.
    received : FrameInfo or None
        Capture metadata of the newest frame handed to :meth:`write`, or
        ``None`` before the first.  Compared with the newest frame the
        camera has captured, it measures how far the writer is behind.

    Notes
    -----
    A writer must not drop frames, so frames queue in memory while storage
    is slower than the camera.  The writer does not police that backlog;
    the code that owns the recording does (see
    :class:`~QVideo.dvr.QDVRWidget.QDVRWidget`).

    Abstract Methods
    ----------------
    open(frame: Image) -> bool
        Open the video file for writing.
    isOpen() -> bool
        Check if the video file is open.
    _write(frame: Image, info: FrameInfo) -> None
        Write a video frame to the file.
    close() -> None
        Close the video file.
    '''

    #: Emitted when a new frame is written, with the current frame number.
    frameNumber = QtCore.Signal(int)
    #: Emitted when video writing is complete.
    finished = QtCore.Signal(str)

    #: Whether the file has one frame size and type.  A writer that can
    #: store frames of different sizes sets this to ``False``.
    fixedSize = True

    def __init__(self,
                 filename: str,
                 fps: int = 24,
                 nframes: int = 10_000,
                 nskip: int = 1,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.filename = filename
        self.fps = fps
        self.framenumber = 0
        self.nskip = nskip
        self.target = nframes
        self.blank = False
        self.received: FrameInfo | None = None
        self._frameType: tuple[tuple[int, ...], np.dtype] | None = None
        self._stopped = False

    @abstractmethod
    def open(self, frame: Image) -> bool:
        '''Open the output file using frame dimensions from the first frame.

        Called automatically by :meth:`write` on the first frame.

        Parameters
        ----------
        frame : Image
            The first video frame; dimensions and color mode are read
            from this array.

        Returns
        -------
        bool
            ``True`` if the file was opened successfully.
        '''

    @abstractmethod
    def isOpen(self) -> bool:
        '''Return ``True`` if the output file is currently open.'''

    @QtCore.Slot(np.ndarray)
    @QtCore.Slot(np.ndarray, object)
    def write(self, frame: Image, info: FrameInfo | None = None) -> None:
        '''Write a video frame.

        Opens the file on the first call, writes every :attr:`nskip`-th
        frame received (starting with the first), and emits
        :attr:`finished` when :attr:`nframes` have been written.
        :attr:`framenumber` counts frames received, written or not.

        The writer stops, with :attr:`finished` saying why (``''`` when all is
        well), when the file
        cannot be opened, when a frame has a size or type other than that
        of the first (unless :attr:`fixedSize` is ``False``), and when
        writing raises an exception.  It then ignores every frame.

        Parameters
        ----------
        frame : Image
            Video frame to write.
        info : FrameInfo, optional
            Capture metadata for *frame*, as emitted by
            :attr:`~QVideo.lib.QVideoSource.newFrame`.  If omitted, the
            frame is stamped with the current time.
        '''
        if self._stopped:
            return
        if info is None:
            info = FrameInfo(self.framenumber, perf_counter())
        self.received = info
        if not self.isOpen() and not self.open(frame):
            logger.warning(f'Could not write to {self.filename}')
            self._stop(f'could not open {self.filename!r}')
            return
        if self._frameType is None:
            self._frameType = frame.shape, frame.dtype
        elif self.fixedSize and (frame.shape,
                                 frame.dtype) != self._frameType:
            self._stop(self._changed(frame))
            return
        if self.framenumber >= self.target * self.nskip:
            self._stop()
            return
        if self.framenumber % self.nskip == 0:
            try:
                self._write(np.zeros_like(frame) if self.blank else frame,
                            info)
            except Exception as error:
                logger.exception(f'Could not write to {self.filename}')
                self._stop(f'{type(error).__name__}: {error}')
                return
            self.frameNumber.emit(self.framenumber // self.nskip + 1)
        self.framenumber += 1

    def _stop(self, reason: str = '') -> None:
        '''Stop writing; *reason* is empty if all is well.'''
        self._stopped = True
        self.finished.emit(reason)

    def _changed(self, frame: Image) -> str:
        '''Describe a frame that differs from the frames of the file.'''
        def describe(shape, dtype):
            size = 'x'.join(str(n) for n in reversed(shape))
            return f'{size} {dtype}'
        return (f'the frame size changed from {describe(*self._frameType)} '
                f'to {describe(frame.shape, frame.dtype)} during the '
                'recording, and a file has only one; a filter or a '
                'resized window may have changed it')

    @abstractmethod
    def _write(self, frame: Image, info: FrameInfo) -> None:
        pass

    @QtCore.Slot()
    @abstractmethod
    def close(self) -> None:
        pass

    @QtCore.Slot()
    def shutdown(self) -> None:
        '''Close the file and end the thread this writer lives in.

        Invoke it through a signal, so that it is queued behind the frames
        already waiting and none of them is lost.  The writer must live
        in a worker thread.
        '''
        self.close()
        self.thread().quit()
