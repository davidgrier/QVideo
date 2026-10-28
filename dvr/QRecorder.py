'''Headless recorder: records the frames of a source to a file.'''
import logging
from pathlib import Path
from qtpy import QtCore
from QVideo.lib import QVideoSource
from . import formats
from .QBacklogMonitor import QBacklogMonitor
from .QHDF5Writer import QHDF5Writer


__all__ = ['QRecorder']


logger = logging.getLogger(__name__)


class QRecorder(QtCore.QObject):

    '''Records the frames of a source to a file, without a window.

    The file is written by the class that :mod:`~QVideo.dvr.formats` has for
    its extension, on a thread of its own, so the camera and the interface
    do not wait for the encoder.  A recorder must not drop frames, so frames
    queue in memory while the writer is slower than the camera; a
    :class:`~QVideo.dvr.QBacklogMonitor.QBacklogMonitor` measures the
    backlog, and by default the recording stops when it passes *lagLimit*,
    so that a slow disk cannot fill memory.  Stopping waits for the writer
    to finish the frames that were captured, so none of them is lost.

    The recorder is a Qt object like any other: the signals of the writer
    and the monitor reach it through the event loop of the application,
    which must be running.  Without one, frames are still written, but the
    backlog is not watched and the recording does not end by itself.

    Parameters
    ----------
    source : QVideoSource or None
        The source that supplies the frames.  Anything with ``newFrame``
        and ``fps`` will do.
    stopWhenBehind : bool
        Stop recording when the writer falls more than *lagLimit* seconds
        behind the camera.  Set ``False`` to record through the backlog.
        Default: ``True``.
    lagLimit : float
        How far [seconds] the writer may fall behind the newest captured
        frame.  Default: ``1.``.
    maxMemory : float or None
        Memory [bytes] that frames waiting for the writer may occupy.  The
        recording is treated as behind as soon as the backlog would exceed
        it, whatever *lagLimit* says.  ``None`` means 80% of the memory
        available when the recording starts.  Default: ``None``.
    parent : QObject or None
        Parent object.

    Signals
    -------
    recording(bool)
        Emitted when recording starts (``True``) or stops (``False``).
    frameNumber(int)
        Emitted with the number of frames recorded so far.
    backlog(float)
        Emitted whenever the backlog changes by 5% of what is allowed,
        as a fraction of the allowance.
    behind(float)
        Emitted once each time the writer falls behind by more than is
        allowed, with the lag in seconds.
    stopped(str)
        Emitted with the reason when the recorder stops a recording by
        itself, just before ``recording(False)``: it fell behind the
        camera, or the writer could not go on (the size of the frames
        changed, the file could not be written).

    Examples
    --------
    Record 300 frames in a script, and quit when they are written::

        app = QCoreApplication([])
        recorder = QRecorder(source)
        recorder.recording.connect(lambda on: on or app.quit())
        recorder.start('run.mkv', nframes=300)
        app.exec()
    '''

    #: Emitted when recording starts (``True``) or stops (``False``).
    recording = QtCore.Signal(bool)
    #: Emitted with the number of frames recorded so far.
    frameNumber = QtCore.Signal(int)
    #: Emitted as the backlog changes, as a fraction of what is allowed.
    backlog = QtCore.Signal(float)
    #: Emitted when the recording falls behind the camera, with the lag [s].
    behind = QtCore.Signal(float)
    #: Emitted with the reason when the recorder stops a recording itself.
    stopped = QtCore.Signal(str)
    _shutdown = QtCore.Signal()

    def __init__(self,
                 source: QVideoSource | None = None,
                 stopWhenBehind: bool = True,
                 lagLimit: float = 1.,
                 maxMemory: float | None = None,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.stopWhenBehind = stopWhenBehind
        self.lagLimit = lagLimit
        self.maxMemory = maxMemory
        self._source = source
        self._writer = None
        self._thread: QtCore.QThread | None = None
        self._nframes = 0
        self._rate = 1.
        self._monitor = QBacklogMonitor(self)
        self._monitor.backlog.connect(self.backlog)
        self._monitor.behind.connect(self.behind)
        self._monitor.behind.connect(self._fellBehind)
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    @property
    def source(self) -> QVideoSource | None:
        '''The source that supplies the frames.

        Setting it stops a recording that is running.
        '''
        return self._source

    @source.setter
    def source(self, source: QVideoSource | None) -> None:
        self.stop()
        self._source = source

    @property
    def nframes(self) -> int:
        '''Number of frames that the current or last recording will have.'''
        return self._nframes

    @property
    def rate(self) -> float:
        '''Frame rate of the current or last recording [frames per second].

        The rate of the camera, divided by the interval at which frames
        were recorded.
        '''
        return self._rate

    def isRecording(self) -> bool:
        '''Return ``True`` if recording is in progress.'''
        return self._writer is not None

    def start(self,
              filename: str,
              nframes: int = 10_000,
              nskip: int = 1,
              overwrite: bool = False) -> None:
        '''Start recording to *filename*.

        The frame rate is read from the source once, here: asking for it
        takes the camera lock, which a camera that waits for its next frame
        holds, so asking for it with every frame would stall the interface.

        Parameters
        ----------
        filename : str
            The file to write.  Its extension chooses the format.
        nframes : int
            The number of frames to record; the recording stops by itself
            when it has them.
        nskip : int
            Record every *nskip*-th frame.  The file declares the frame
            rate of the source, so it plays *nskip* times faster, a
            time-lapse.
        overwrite : bool
            Replace *filename* if it exists.  By default an existing file
            is an error, so that a recording cannot destroy another.

        Raises
        ------
        ValueError
            If the extension of *filename* is not supported.
        RuntimeError
            If there is no source, or a recording is already running.
        FileExistsError
            If *filename* exists and *overwrite* is ``False``.
        '''
        if self._source is None:
            raise RuntimeError('there is no source to record')
        if self.isRecording():
            raise RuntimeError('a recording is already running')
        writer_class = formats.writerClass(filename)
        if not overwrite and Path(filename).exists():
            raise FileExistsError(
                f'{filename!r} exists; use overwrite=True to replace it')
        fps = self._source.fps
        writer = writer_class(filename, fps=fps,
                              nframes=nframes, nskip=nskip)
        self._writer = writer
        self._nframes, self._rate = writer.target, fps / nskip
        self._monitor.start(writer, fps, self.lagLimit, self.maxMemory)
        writer.frameNumber.connect(self.frameNumber)
        writer.finished.connect(self._writerFinished)
        self._thread = QtCore.QThread()
        writer.moveToThread(self._thread)
        self._shutdown.connect(writer.shutdown)
        self._thread.start()
        self._source.newFrame.connect(writer.write)
        self._source.newFrame.connect(self._monitor.check)
        self.recording.emit(True)

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop recording, after the frames that were captured are written.

        It does nothing if no recording is running, so it may be called
        again, and it is called when the application is about to quit.
        '''
        if not self.isRecording():
            return
        logger.debug('Stopping recording')
        try:
            self._source.newFrame.disconnect(self._writer.write)
            self._source.newFrame.disconnect(self._monitor.check)
            self._writer.frameNumber.disconnect(self.frameNumber)
            self._writer.finished.disconnect(self._writerFinished)
        except (RuntimeError, TypeError):
            logger.debug('Some recording signals were already disconnected')
        self._monitor.stop()
        self._shutdown.emit()  # queued behind the frames already captured
        self._thread.wait()
        self._thread = None
        self._writer = None
        self.recording.emit(False)

    @QtCore.Slot(str)
    def _writerFinished(self, reason: str) -> None:
        '''Stop the recording, saying why if the writer could not go on.'''
        if not self.isRecording():
            return
        if reason:
            logger.error(reason)
            self.stopped.emit(reason)
        self.stop()

    def _fellBehind(self, lag: float) -> None:
        '''Stop the recording, if that is the policy, as it falls behind.'''
        if self.stopWhenBehind:
            reason = (f'recording fell {lag:.1f} s behind the camera; '
                      + self._remedy())
            logger.error(reason)
            self.stopped.emit(reason)
            self.stop()

    def _remedy(self) -> str:
        '''Suggest what to try when the writer cannot keep up.'''
        if isinstance(self._writer, QHDF5Writer):
            return 'use a faster disk, or lower the frame size or rate'
        if formats.pyav_available:
            return 'lower the frame size or rate'
        return 'install QVideo[av], or lower the frame size or rate'
