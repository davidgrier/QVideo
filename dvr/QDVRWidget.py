'''Composite DVR widget for recording and playing back video streams.'''
import importlib.util
import math
from qtpy import QtCore, QtGui, QtWidgets
from pathlib import Path
import numpy as np
import psutil
from QVideo.lib import clickable, QVideoSource
from QVideo.lib.videotypes import Image, FrameInfo
from .QOpenCVWriter import QOpenCVWriter
from .QOpenCVReader import QOpenCVSource

from .QHDF5Writer import QHDF5Writer
from .QHDF5Reader import QHDF5Source

import logging


__all__ = ['QDVRWidget']

#: Steps in which the backlog is reported.
_BACKLOG_STEPS = 20

_h5py_available = importlib.util.find_spec('h5py') is not None


logger = logging.getLogger(__name__)

try:
    from .icons_rc import *
except Exception:  # pragma: no cover
    logger.debug(
        'Could not load DVR icons; buttons will show text labels only')


class QDVRWidget(QtWidgets.QFrame):

    '''Widget providing record, play, pause, stop and rewind controls
    for a digital video recorder.

    Connects to a :class:`~QVideo.lib.QVideoSource.QVideoSource` to
    capture incoming frames to a file, and can play back previously
    recorded files.  Supported formats are determined by the
    :attr:`Writer` and :attr:`Player` class attributes; by default
    AVI (``.avi``), MKV (``.mkv``), and MP4 (``.mp4``) are supported;
    HDF5 (``.h5``) is also supported when ``h5py`` is installed.
    Requesting an unsupported extension is logged
    as an error and silently ignored.

    Recording and playback stop automatically when the widget is closed
    or the application is about to quit.

    Parameters
    ----------
    source : QVideoSource or None
        Video source supplying frames to record.
    filename : str or None
        Default file path for saving.  If ``None``, defaults to
        ``~/default.mkv``.
    stopWhenBehind : bool
        Stop recording when the writer falls more than *lagLimit* seconds
        behind the camera.  A recorder must not drop frames, so frames
        queue in memory while storage is slower than the camera; stopping
        keeps a slow disk from filling memory.  Set ``False`` to record
        through the backlog.  Default: ``True``.
    lagLimit : float
        How far [seconds] the writer may fall behind the newest captured
        frame.  Default: ``1.``.
    maxMemory : float or None
        Memory [bytes] that frames waiting for the writer may occupy.
        The recording is treated as behind as soon as the backlog would
        exceed it, whatever *lagLimit* says.  ``None`` means 80% of the
        memory available when recording starts.  Default: ``None``.
    *args :
        Forwarded to :class:`~qtpy.QtWidgets.QFrame`.
    **kwargs :
        Forwarded to :class:`~qtpy.QtWidgets.QFrame`.

    Signals
    -------
    newFrame(Image)
        Emitted for each frame during playback.
    recording(bool)
        Emitted when recording starts (``True``) or stops (``False``).
    playing(bool)
        Emitted when playback starts (``True``) or stops (``False``).
    backlog(float)
        Emitted while recording whenever the backlog changes by 5% of what
        is allowed, with the backlog as a fraction of the allowance:
        ``1.`` is the point at which ``behind`` is emitted.
    behind(float)
        Emitted once each time the recording falls behind the camera by
        more than *lagLimit* seconds or *maxMemory* bytes, with the lag
        in seconds.
    stopped(str)
        Emitted with the reason when the widget stops a recording by
        itself, just before ``recording(False)``.

    Notes
    -----
    Stopping waits for the writer to finish the frames already captured,
    so no recorded frame is lost.  With *stopWhenBehind* the wait is
    bounded by the smaller of *lagLimit* seconds and *maxMemory* bytes of
    data.
    '''

    #: Emitted for each frame during playback.
    newFrame = QtCore.Signal(np.ndarray)
    #: Emitted when recording starts (``True``) or stops (``False``).
    recording = QtCore.Signal(bool)
    #: Emitted when playback starts (``True``) or stops (``False``).
    playing = QtCore.Signal(bool)
    #: Emitted as the backlog changes, as a fraction of what is allowed.
    backlog = QtCore.Signal(float)
    #: Emitted when the recording falls behind the camera, with the lag [s].
    behind = QtCore.Signal(float)
    #: Emitted with the reason when the widget stops a recording itself.
    stopped = QtCore.Signal(str)
    _shutdown = QtCore.Signal()

    FILENAME = 'default.mkv'

    Writer: dict[str, type] = {'.avi': QOpenCVWriter,
                                '.mkv': QOpenCVWriter,
                                '.mp4': QOpenCVWriter}
    Player: dict[str, type] = {'.avi': QOpenCVSource,
                                '.mkv': QOpenCVSource,
                                '.mp4': QOpenCVSource}

    FileGroups: dict[str, set[str]] = {
        'Lossless Video': {'.avi', '.mkv'},
        'Video': {'.mp4'}}

    if _h5py_available:
        Writer['.h5'] = QHDF5Writer
        Player['.h5'] = QHDF5Source
        FileGroups['HDF5 files'] = {'.h5'}

    @classmethod
    def _buildFilter(cls, save: bool) -> str:
        '''Build a file-dialog filter string from supported formats.

        Parameters
        ----------
        save : bool
            If ``True``, derive extensions from :attr:`Writer`;
            otherwise from :attr:`Player`.

        Returns
        -------
        str
            A ``;;``-separated filter string suitable for
            ``QFileDialog``, with extensions grouped by
            :attr:`FileGroups`.
        '''
        formats = set(cls.Writer if save else cls.Player)
        parts = []
        covered = set()
        for label, exts in cls.FileGroups.items():
            matching = sorted(exts & formats)
            if matching:
                covered |= set(matching)
                parts.append(
                    f'{label} ({" ".join("*" + e for e in matching)})')
        ungrouped = sorted(formats - covered)
        if ungrouped:
            parts.append(
                f'Other files ({" ".join("*" + e for e in ungrouped)})')
        return ';;'.join(parts) if parts else 'All files (*)'

    def __init__(self,
                 *args,
                 source: QVideoSource | None = None,
                 filename: str = '',
                 stopWhenBehind: bool = True,
                 lagLimit: float = 1.,
                 maxMemory: float | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.stopWhenBehind = stopWhenBehind
        self.lagLimit = lagLimit
        self.maxMemory = maxMemory
        self._budget = float('inf')
        self._source: QVideoSource | None = None
        self._writer: object | None = None
        self._player: QVideoSource | None = None
        self._thread: QtCore.QThread | None = None
        self._level = 0
        self._setupUi()
        self._connectSignals()
        self.source = source
        self.filename = filename if filename else str(
            Path.home() / self.FILENAME)

    def _button(self,
                text: str,
                tip: str,
                icon: str,
                shortcut: str | None = None) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text, self)
        button.setStatusTip(tip)
        button.setIcon(QtGui.QIcon(f':/icons/icons/{icon}.svg'))
        if shortcut:
            button.setShortcut(shortcut)
        return button

    def _fileRow(self,
                 text: str,
                 tip: str) -> tuple[QtWidgets.QHBoxLayout,
                                    QtWidgets.QLineEdit]:
        edit = QtWidgets.QLineEdit(self)
        edit.setReadOnly(True)
        edit.setStatusTip(tip)
        label = QtWidgets.QLabel(text, self)
        label.setBuddy(edit)
        return self._row(6, (6, 0, 6, 0), label, edit), edit

    def _spinBox(self,
                 text: str,
                 tip: str,
                 minimum: int,
                 maximum: int) -> tuple[QtWidgets.QLabel,
                                        QtWidgets.QSpinBox]:
        spinBox = QtWidgets.QSpinBox(self)
        spinBox.setToolTip(tip)
        spinBox.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        spinBox.setRange(minimum, maximum)
        label = QtWidgets.QLabel(text, self)
        label.setBuddy(spinBox)
        return label, spinBox

    @staticmethod
    def _row(spacing: int,
             margins: tuple[int, int, int, int],
             *widgets: QtWidgets.QWidget) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(spacing)
        row.setContentsMargins(*margins)
        for widget in widgets:
            row.addWidget(widget)
        return row

    def _setupUi(self) -> None:
        self.setFrameShape(QtWidgets.QFrame.Shape.Box)

        self.recordButton = self._button(
            '&Record', 'Record video', 'media-record', 'R')
        self.stopButton = self._button(
            '&Stop', 'Stop recording', 'media-playback-stop', 'S')
        self.frameNumber = QtWidgets.QLCDNumber(self)
        self.frameNumber.setSegmentStyle(
            QtWidgets.QLCDNumber.SegmentStyle.Flat)
        recordRow = self._row(2, (0, 0, 6, 0), self.recordButton,
                              self.stopButton, self.frameNumber)

        self.rewindButton = self._button(
            '&Rewind', 'Rewind video file', 'media-skip-backward')
        self.pauseButton = self._button(
            '&Pause', 'Pause video playback', 'media-playback-pause')
        self.playButton = self._button(
            'P&lay', 'Play video file', 'media-playback-start')
        playRow = self._row(2, (0, 1, 0, 1), self.rewindButton,
                            self.pauseButton, self.playButton)

        saveRow, self.saveEdit = self._fileRow('Save As', 'Video file name')
        playFileRow, self.playEdit = self._fileRow('Play', 'Video file')

        durationLabel, self.nframes = self._spinBox(
            'Duration', 'number of frames to record', 10, 99000)
        self.nframes.setSingleStep(10)
        self.nframes.setValue(10000)
        intervalLabel, self.nskip = self._spinBox(
            'Interval',
            'Record every Nth frame; the video plays N times faster',
            1, 999)
        framesRow = self._row(6, (6, 4, 6, 4), durationLabel, self.nframes,
                              intervalLabel, self.nskip)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)
        for row in (recordRow, saveRow, playRow, playFileRow, framesRow):
            layout.addLayout(row)

    def _connectSignals(self) -> None:
        clickable(self.playEdit).connect(lambda: self.getFileName(False))
        clickable(self.saveEdit).connect(lambda: self.getFileName(True))
        self.recordButton.clicked.connect(self.record)
        self.stopButton.clicked.connect(self.stop)
        self.rewindButton.clicked.connect(self.rewind)
        self.pauseButton.clicked.connect(self.pause)
        self.playButton.clicked.connect(self.play)
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.stop)

    def isRecording(self) -> bool:
        '''Return ``True`` if recording is in progress.'''
        return self._writer is not None

    def isPlaying(self) -> bool:
        '''Return ``True`` if playback is in progress.'''
        return self._player is not None

    def isPaused(self) -> bool:
        '''Return ``True`` if playback is paused.'''
        return self.isPlaying() and self._player.isPaused()

    def getFileName(self, save: bool = False) -> str:
        '''Open a file dialog and update the filename fields.

        Parameters
        ----------
        save : bool
            If ``True``, open a save dialog; otherwise open an open
            dialog.

        Returns
        -------
        str
            Selected filename, or empty string if cancelled.
        '''
        if self.isPlaying() or self.isRecording():
            return ''
        get = (QtWidgets.QFileDialog.getSaveFileName if save
               else QtWidgets.QFileDialog.getOpenFileName)
        filename, _ = get(
            self, 'Video File Name', str(self.filename),
            self._buildFilter(save),
            options=QtWidgets.QFileDialog.Option.DontUseNativeDialog)
        if filename:
            if save:
                self.filename = filename
            else:
                self.playname = filename
        return filename

    @QtCore.Slot()
    def record(self) -> None:
        '''Start recording, or stop if already recording.

        Does nothing if ``source`` is ``None``, if playback is active,
        or if the save filename has an unsupported extension.
        '''
        if self.source is None or self.isPlaying():
            return
        if self.isRecording():
            self.stop()
            return
        if not (self.filename or self.getFileName(save=True)):
            return
        suffix = Path(self.filename).suffix
        if suffix not in self.Writer:
            logger.error(f'Unsupported file format: {suffix!r}')
            return
        logger.debug(f'Recording: {self.filename}')
        self._startWriter(self.Writer[suffix])
        self.recording.emit(True)

    def _startWriter(self, writer_class: type) -> None:
        '''Create the writer, run it on its own thread and feed it frames.'''
        self._writer = writer_class(self.filename,
                                    fps=self.source.fps,
                                    nframes=self.nframes.value(),
                                    nskip=self.nskip.value())
        self._level = 0
        self._budget = (self.maxMemory
                        or 0.8 * psutil.virtual_memory().available)
        self._writer.frameNumber.connect(self.setFrameNumber)
        self._writer.finished.connect(self.stop)
        self._thread = QtCore.QThread()
        self._writer.moveToThread(self._thread)
        self._shutdown.connect(self._writer.shutdown)
        self._thread.start()
        self.source.newFrame.connect(self._writer.write)
        self.source.newFrame.connect(self._watch)

    @QtCore.Slot()
    def play(self) -> None:
        '''Start playback, or resume if paused.

        Does nothing if recording is active, if playback is already
        running, or if the playback filename has an unsupported
        extension.
        '''
        if self.isPaused():
            self._player.resume()
            return
        if self.isRecording() or self.isPlaying():
            return
        if not (self.playname or self.getFileName(save=False)):
            return
        suffix = Path(self.playname).suffix
        if suffix not in self.Player:
            logger.error(f'Unsupported file format: {suffix!r}')
            return
        self.framenumber = 0
        logger.debug(f'Starting Playback: {self.playname}')
        player_class = self.Player[suffix]
        self._player = player_class(self.playname)
        if self._player.isOpen():
            logger.debug('connecting signals')
            self._player.newFrame.connect(self.stepFrameNumber)
            self._player.newFrame.connect(self.newFrame)
            self.playing.emit(True)
            self._player.start()
        else:
            self._player = None

    @QtCore.Slot()
    def pause(self) -> None:
        '''Pause or resume playback.'''
        if self.isPlaying():
            self._player.resume() if self.isPaused() else self._player.pause()

    @QtCore.Slot()
    def rewind(self) -> None:
        '''Rewind to the first frame and pause.'''
        if self.isPlaying():
            self._player.source.rewind()
            self._player.pause()
            self.framenumber = 0

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop recording or playback.'''
        self._stopRecording()
        self._stopPlayback()
        self.framenumber = 0

    def _stopRecording(self) -> None:
        if not self.isRecording():
            return
        logger.debug('Stopping Recording')
        try:
            self.source.newFrame.disconnect(self._writer.write)
            self.source.newFrame.disconnect(self._watch)
            self._writer.frameNumber.disconnect(self.setFrameNumber)
            self._writer.finished.disconnect(self.stop)
        except (RuntimeError, TypeError):
            logger.debug('Some recording signals were already disconnected')
        self._shutdown.emit()
        self._thread.wait()
        self._thread = None
        self._writer = None
        self.recording.emit(False)

    def _stopPlayback(self) -> None:
        if not self.isPlaying():
            return
        logger.debug('Stopping Playback')
        try:
            self._player.newFrame.disconnect(self.stepFrameNumber)
            self._player.newFrame.disconnect(self.newFrame)
        except (RuntimeError, TypeError):
            logger.debug('Playback signal was already disconnected')
        self._player.stop()
        self._player = None
        self.playing.emit(False)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop recording or playback when the widget is closed.'''
        self.stop()
        super().closeEvent(event)

    @QtCore.Slot(np.ndarray)
    @QtCore.Slot(np.ndarray, object)
    def _watch(self, frame: Image, info: FrameInfo | None = None) -> None:
        '''Compare each captured frame with the newest one the writer has
        taken up, report the backlog, and report once each time the writer
        falls behind.

        The comparison uses the capture times, so it measures the backlog
        even while the writer is stuck inside a single write, and it
        ignores sources that capture slowly.  The memory budget is
        converted to the time it takes the camera to fill it, so one
        limit serves both.  The backlog is reported in steps, not for
        every frame.
        '''
        taken = self._writer and self._writer.received
        if info is None or not taken:
            return
        lag = max(info.timestamp - taken.timestamp, 0.)
        fill = self._budget / (self.source.fps * frame.nbytes)
        fraction = lag / min(self.lagLimit, fill)
        level = math.ceil(fraction * _BACKLOG_STEPS)
        if level == self._level:
            return
        was, self._level = self._level, level
        self.backlog.emit(fraction)
        if level > _BACKLOG_STEPS >= was:
            self.behind.emit(lag)
            if self.stopWhenBehind:
                reason = f'recording fell {lag:.1f} s behind the camera'
                logger.error(reason)
                self.stopped.emit(reason)
                self.stop()

    @QtCore.Slot(int)
    def setFrameNumber(self, framenumber: int) -> None:
        '''Set the displayed frame number.'''
        self.framenumber = framenumber

    @QtCore.Slot()
    def stepFrameNumber(self) -> None:
        '''Increment the displayed frame number.'''
        self.framenumber += 1

    @property
    def source(self) -> QVideoSource | None:
        '''The :class:`~QVideo.lib.QVideoSource.QVideoSource` being
        recorded.'''
        return self._source

    @source.setter
    def source(self, source: QVideoSource | None) -> None:
        '''Set the video source.  Disables the record button when ``None``.'''
        logger.debug(f'Setting source {type(source)}')
        self._source = source
        self.recordButton.setDisabled(source is None)

    @property
    def player(self) -> QVideoSource | None:
        '''The active playback source, or ``None`` when not playing.'''
        return self._player

    @QtCore.Property(str)
    def filename(self) -> str:
        '''Current save filename.'''
        return str(self.saveEdit.text())

    @filename.setter
    def filename(self, filename: str | None) -> None:
        if filename is None:
            return
        if not (self.isRecording() or self.isPlaying()):
            self.saveEdit.setText(filename)
            self.playname = filename

    @QtCore.Property(str)
    def playname(self) -> str:
        '''Current playback filename.'''
        return str(self.playEdit.text())

    @playname.setter
    def playname(self, filename: str) -> None:
        if not self.isPlaying():
            self.playEdit.setText(filename)

    @property
    def framenumber(self) -> int:
        '''Current frame number displayed in the LCD.'''
        return self.frameNumber.intValue()

    @framenumber.setter
    def framenumber(self, number: int) -> None:
        self.frameNumber.display(number)
