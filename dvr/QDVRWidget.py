'''Composite DVR widget for recording and playing back video streams.'''
import functools
import importlib.util
import os
from qtpy import QtCore, QtGui, QtWidgets
from pathlib import Path
import numpy as np
from QVideo.lib import clickable, QVideoSource
from .QBacklogMonitor import QBacklogMonitor
from .QOpenCVWriter import QOpenCVWriter
from .QOpenCVReader import QOpenCVSource
from .QPyAVWriter import QPyAVWriter
from .QPyAVReader import QPyAVSource

from .QHDF5Writer import QHDF5Writer
from .QHDF5Reader import QHDF5Source

import logging


__all__ = ['QDVRWidget']

_h5py_available = importlib.util.find_spec('h5py') is not None
_pyav_available = importlib.util.find_spec('av') is not None


logger = logging.getLogger(__name__)


@functools.cache
def _record() -> QtGui.QIcon:
    '''Return the Tango record icon, which Qt does not provide.'''
    return QtGui.QIcon(str(Path(__file__).parent / 'icons' / 'record.svg'))


_Icon = QtWidgets.QStyle.StandardPixmap


def _clock(seconds: float) -> str:
    '''Format *seconds* as ``m:ss.s``.'''
    return f'{int(seconds // 60)}:{seconds % 60:04.1f}'


class QDVRWidget(QtWidgets.QFrame):

    '''Widget providing the controls of a digital video recorder: record,
    stop, rewind, frame step, play/pause and a position slider.

    Connects to a :class:`~QVideo.lib.QVideoSource.QVideoSource` to
    capture incoming frames to a file, and can play back previously
    recorded files.  Supported formats are determined by the
    :attr:`Writer` and :attr:`Player` class attributes; by default
    AVI (``.avi``), MKV (``.mkv``), and MP4 (``.mp4``) are supported, by
    PyAV if it is installed and by OpenCV if not;
    HDF5 (``.h5``) is also supported when ``h5py`` is installed.
    To use OpenCV although PyAV is installed, set the entries of
    :attr:`Writer` and :attr:`Player` to the OpenCV classes.
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
    A :class:`~QVideo.dvr.QBacklogMonitor.QBacklogMonitor` measures the
    backlog; the widget forwards its signals and decides whether to stop.
    The limits are read when a recording starts.

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

    if _pyav_available:
        Writer.update(dict.fromkeys(('.avi', '.mkv', '.mp4'), QPyAVWriter))
        Player.update(dict.fromkeys(('.avi', '.mkv', '.mp4'), QPyAVSource))

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
        self._monitor = QBacklogMonitor(self)
        self._source: QVideoSource | None = None
        self._writer: object | None = None
        self._player: QVideoSource | None = None
        self._thread: QtCore.QThread | None = None
        self._length = 0
        self._fps = 1.  # of the video that plays
        self._setupUi()
        self._connectSignals()
        self.source = source
        self.filename = filename if filename else str(
            Path.home() / self.FILENAME)

    def _button(self,
                tip: str,
                icon: QtGui.QIcon,
                shortcut: str | None = None) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(self)
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(24, 24))
        button.setToolTip(tip)
        button.setStatusTip(tip)
        if shortcut:
            button.setShortcut(shortcut)
        return button

    def _icon(self, icon: _Icon) -> QtGui.QIcon:
        '''Return an icon of the style in the color of the button text.

        The icons of a style are black in many styles, which is hard to
        see on a dark theme.
        '''
        ratio = self.devicePixelRatioF()
        side = round(24 * ratio)
        pixmap = self.style().standardIcon(icon).pixmap(side, side)
        painter = QtGui.QPainter(pixmap)
        painter.setCompositionMode(
            QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), self.palette().buttonText())
        painter.end()
        pixmap.setDevicePixelRatio(ratio)
        return QtGui.QIcon(pixmap)

    def _label(self, alignment=QtCore.Qt.AlignmentFlag.AlignLeft):
        label = QtWidgets.QLabel(self)
        label.setAlignment(alignment)
        label.setFont(QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.SystemFont.FixedFont))
        return label

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

        self.recordButton = self._button('Record video', _record(), 'R')
        if self.recordButton.icon().pixmap(24, 24).isNull():
            self.recordButton.setText('Record')  # no SVG support in Qt
        self.stopButton = self._button(
            'Stop recording or playback', self._icon(_Icon.SP_MediaStop), 'S')
        self.rewindButton = self._button(
            'Go to the first frame', self._icon(_Icon.SP_MediaSkipBackward))
        self.backButton = self._button(
            'Back one frame', self._icon(_Icon.SP_MediaSeekBackward))
        self.playButton = self._button('Play', self._icon(_Icon.SP_MediaPlay))
        self.forwardButton = self._button(
            'Forward one frame', self._icon(_Icon.SP_MediaSeekForward))
        transportRow = self._row(
            2, (0, 0, 0, 0), self.recordButton, self.stopButton,
            self.rewindButton, self.backButton, self.playButton,
            self.forwardButton)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.positionLabel = self._label()
        self.timeLabel = self._label(QtCore.Qt.AlignmentFlag.AlignRight)
        statusRow = self._row(6, (6, 0, 6, 0), self.positionLabel,
                              self.timeLabel)

        self.fileEdit = QtWidgets.QLineEdit(self)
        self.fileEdit.setReadOnly(True)
        self.fileEdit.setStatusTip('Video file name')
        fileLabel = QtWidgets.QLabel('File', self)
        fileLabel.setBuddy(self.fileEdit)
        fileRow = self._row(6, (6, 0, 6, 0), fileLabel, self.fileEdit)

        durationLabel, self.nframes = self._spinBox(
            'Duration', 'number of frames to record', 10, 99000)
        self.nframes.setSingleStep(10)
        self.nframes.setValue(10000)
        intervalLabel, self.nskip = self._spinBox(
            'Interval',
            'Record every Nth frame; the video plays N times faster',
            1, 999)
        framesBox = QtWidgets.QFrame(self)
        framesBox.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        framesBox.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        framesBox.setLayout(self._row(6, (6, 4, 6, 4), durationLabel,
                                      self.nframes, intervalLabel,
                                      self.nskip))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(fileRow)
        layout.addLayout(transportRow)
        layout.addWidget(self.slider)
        layout.addLayout(statusRow)
        layout.addWidget(framesBox)
        self._display(0, 0, 1.)

    def _connectSignals(self) -> None:
        clickable(self.fileEdit).connect(self.getFileName)
        self.recordButton.clicked.connect(self.record)
        self.stopButton.clicked.connect(self.stop)
        self.rewindButton.clicked.connect(self.rewind)
        self.backButton.clicked.connect(lambda: self.step(-1))
        self.playButton.clicked.connect(self._togglePlay)
        self.forwardButton.clicked.connect(lambda: self.step(1))
        self.slider.valueChanged.connect(lambda n: self.seek(n - 1))
        self._monitor.backlog.connect(self.backlog)
        self._monitor.behind.connect(self.behind)
        self._monitor.behind.connect(self._fellBehind)
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.stop)

    def _updateUi(self) -> None:
        '''Enable the controls that make sense and show play or pause.'''
        recording, playing = self.isRecording(), self.isPlaying()
        running = playing and not self.isPaused()
        self.recordButton.setEnabled(self.source is not None and not playing)
        self.stopButton.setEnabled(recording or playing)
        self.playButton.setEnabled(not recording)
        for widget in (self.rewindButton, self.backButton,
                       self.forwardButton):
            widget.setEnabled(playing)
        # An idle or recording slider is shown, but it does not respond.
        Qt = QtCore.Qt
        self.slider.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, not playing)
        self.slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus if playing
                                   else Qt.FocusPolicy.NoFocus)
        self.playButton.setIcon(self._icon(
            _Icon.SP_MediaPause if running else _Icon.SP_MediaPlay))
        self.playButton.setToolTip('Pause' if running else 'Play')

    def _display(self, done: int, total: int, rate: float) -> None:
        '''Show *done* of *total* frames, which arrive at *rate* [fps].'''
        with QtCore.QSignalBlocker(self.slider):
            self.slider.setRange(0, max(total, 1))  # an empty range is blank
            if not self.slider.isSliderDown():
                self.slider.setValue(done)
        self.positionLabel.setText(f'frame {done} / {total}')
        self.timeLabel.setText(
            f'{_clock(done / rate)} / {_clock(total / rate)}')

    def isRecording(self) -> bool:
        '''Return ``True`` if recording is in progress.'''
        return self._writer is not None

    def isPlaying(self) -> bool:
        '''Return ``True`` if playback is in progress.'''
        return self._player is not None

    def isPaused(self) -> bool:
        '''Return ``True`` if playback is paused.'''
        return self.isPlaying() and self._player.isPaused()

    def getFileName(self) -> str:
        '''Open a file dialog and set the file name.

        The same file serves for recording and playback.  The dialog does
        not ask before replacing a file, because it may be choosing a
        file to play: :meth:`record` asks instead.

        Returns
        -------
        str
            Selected filename, or empty string if cancelled.
        '''
        if self.isPlaying() or self.isRecording():
            return ''
        Option = QtWidgets.QFileDialog.Option
        dialog = QtWidgets.QFileDialog(self, 'Select Video File')
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        dialog.setOptions(Option.DontUseNativeDialog |
                          Option.DontConfirmOverwrite)
        dialog.setLabelText(QtWidgets.QFileDialog.DialogLabel.Accept,
                            'Select')
        dialog.setNameFilter(self._buildFilter(True))
        dialog.selectFile(self.filename)
        if not dialog.exec():
            return ''
        self.filename = dialog.selectedFiles()[0]
        return self.filename

    def _warn(self, text: str) -> None:
        QtWidgets.QMessageBox.warning(self, 'Video file', text)

    def _mayRecord(self) -> bool:
        '''Return whether it is safe to write to :attr:`filename`.

        Warns when the file or its folder cannot be written, and asks
        before replacing a file that exists.
        '''
        path = Path(self.filename)
        if not path.exists():
            if os.access(path.parent, os.W_OK):
                return True
            self._warn(f'The folder {path.parent} does not exist or '
                       'cannot be written to.')
            return False
        if not os.access(path, os.W_OK):
            self._warn(f'{path.name} is read-only.')
            return False
        Button = QtWidgets.QMessageBox.StandardButton
        answer = QtWidgets.QMessageBox.question(
            self, 'Record', f'{path.name} already exists.  Replace it?',
            Button.Yes | Button.No, Button.No)
        return answer == Button.Yes

    @QtCore.Slot()
    def record(self) -> None:
        '''Start recording, or stop if already recording.

        Does nothing if ``source`` is ``None``, if playback is active,
        or if the filename has an unsupported extension.  Warns, and does
        not record, if the file cannot be written; asks before replacing
        a file that exists.
        '''
        if self.source is None or self.isPlaying():
            return
        if self.isRecording():
            self.stop()
            return
        writer_class = self._handler(self.Writer)
        if writer_class is None or not self._mayRecord():
            return
        logger.debug(f'Recording: {self.filename}')
        self._startWriter(writer_class)
        self.recording.emit(True)
        self._updateUi()

    def _handler(self, table: dict[str, type]) -> type | None:
        '''Return the class of *table* for the file name, or ``None``.

        Asks for a file name if there is none, and logs an extension that
        the table does not have.
        '''
        if not (self.filename or self.getFileName()):
            return None
        suffix = Path(self.filename).suffix
        if suffix not in table:
            logger.error(f'Unsupported file format: {suffix!r}')
        return table.get(suffix)

    def _startWriter(self, writer_class: type) -> None:
        '''Create the writer, run it on its own thread and feed it frames.

        The frame rate is read from the camera once, here: asking for it
        takes the camera lock, which a camera that waits for its next frame
        holds, so asking for it with every frame would stall the GUI.
        '''
        fps = self.source.fps
        self._writer = writer_class(self.filename, fps=fps,
                                    nframes=self.nframes.value(),
                                    nskip=self.nskip.value())
        self._monitor.start(self._writer, fps, self.lagLimit, self.maxMemory)
        self._writer.frameNumber.connect(self._setFrameNumber)
        self._writer.finished.connect(self.stop)
        self._thread = QtCore.QThread()
        self._writer.moveToThread(self._thread)
        self._shutdown.connect(self._writer.shutdown)
        self._thread.start()
        self.source.newFrame.connect(self._writer.write)
        self.source.newFrame.connect(self._monitor.check)
        self._display(0, self._writer.target, fps)

    @QtCore.Slot()
    def play(self) -> None:
        '''Start playback, or resume if paused.

        Does nothing if recording is active or playback is already
        running.  Warns, and does not play, if the file does not exist.
        A paused video that has reached its end starts over.
        '''
        if self.isPaused():
            if 0 < self._length <= self.framenumber:
                self._player.seek(0)
            self._player.resume()
            self._updateUi()
            return
        if self.isRecording() or self.isPlaying():
            return
        player_class = self._handler(self.Player)
        if player_class is None:
            return
        if not Path(self.filename).is_file():
            self._warn(f'There is no file {Path(self.filename).name} '
                       'to play.')
            return
        self._startPlayer(player_class)

    def _startPlayer(self, player_class: type) -> None:
        '''Open the file, play it on its own thread and follow it.'''
        logger.debug(f'Starting Playback: {self.filename}')
        player = player_class(self.filename)
        if not player.isOpen():
            return
        self._player = player
        reader = player.source
        self._length, self._fps = reader.length, reader.fps
        self._display(0, self._length, self._fps)
        player.newFrame.connect(self._follow)
        player.newFrame.connect(self.newFrame)
        self.playing.emit(True)
        player.start()
        self._updateUi()

    @QtCore.Slot()
    def pause(self) -> None:
        '''Pause playback.  :meth:`play` resumes it.'''
        if self.isPlaying():
            self._player.pause()
            self._updateUi()

    def _togglePlay(self) -> None:
        if self.isPlaying() and not self.isPaused():
            self.pause()
        else:
            self.play()

    @QtCore.Slot(int)
    def seek(self, framenumber: int) -> None:
        '''Go to frame *framenumber* (zero-based) of the video.

        The video keeps playing, or stays paused, as it was.
        '''
        if self.isPlaying():
            framenumber = max(framenumber, 0)
            if self._length:
                framenumber = min(framenumber, self._length - 1)
            self._player.seek(framenumber)

    def _pauseAt(self, framenumber: int) -> None:
        self.pause()
        self.seek(framenumber)

    @QtCore.Slot()
    def rewind(self) -> None:
        '''Go to the first frame and pause.'''
        self._pauseAt(0)

    def step(self, frames: int = 1) -> None:
        '''Pause and move *frames* frames forward, or back if negative.'''
        self._pauseAt(self.framenumber - 1 + frames)

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop recording or playback.'''
        self._stopRecording()
        self._stopPlayback()
        self._display(0, 0, 1.)
        self._updateUi()

    def _stopRecording(self) -> None:
        if not self.isRecording():
            return
        logger.debug('Stopping Recording')
        try:
            self.source.newFrame.disconnect(self._writer.write)
            self.source.newFrame.disconnect(self._monitor.check)
            self._writer.frameNumber.disconnect(self._setFrameNumber)
            self._writer.finished.disconnect(self.stop)
        except (RuntimeError, TypeError):
            logger.debug('Some recording signals were already disconnected')
        self._monitor.stop()
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
            self._player.newFrame.disconnect(self._follow)
            self._player.newFrame.disconnect(self.newFrame)
        except (RuntimeError, TypeError):
            logger.debug('Playback signal was already disconnected')
        self._player.stop()
        self._player.wait()
        self._player = None
        self.playing.emit(False)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop recording or playback when the widget is closed.'''
        self.stop()
        super().closeEvent(event)

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
        tips = ['record to .h5' if '.h5' in self.Writer
                else 'install QVideo[dvr] to record to .h5']
        if not _pyav_available:
            tips.append('install QVideo[av]')
        tips.append('lower the frame size or rate')
        return ', or '.join(tips)

    @QtCore.Slot(int)
    def _setFrameNumber(self, framenumber: int) -> None:
        '''Show that *framenumber* frames have been recorded.'''
        if self.isRecording():  # one may arrive after the recording stops
            writer = self._writer
            self._display(framenumber, writer.target,
                          writer.fps / writer.nskip)

    def _follow(self) -> None:
        '''Show where playback is; pause at the end of the video.'''
        if not self.isPlaying():
            return
        done = self._player.source.framenumber
        self._display(done, max(self._length, done), self._fps)
        if 0 < self._length <= done and not self.isPaused():
            self._player.pause()
            self._updateUi()

    @property
    def source(self) -> QVideoSource | None:
        '''The :class:`~QVideo.lib.QVideoSource.QVideoSource` being
        recorded.  Without one (``None``) the record button is disabled.'''
        return self._source

    @source.setter
    def source(self, source: QVideoSource | None) -> None:
        logger.debug(f'Setting source {type(source)}')
        self._source = source
        self._updateUi()

    @property
    def player(self) -> QVideoSource | None:
        '''The active playback source, or ``None`` when not playing.'''
        return self._player

    @property
    def filename(self) -> str:
        '''Name of the file to record to and to play.'''
        return str(self.fileEdit.text())

    @filename.setter
    def filename(self, filename: str | None) -> None:
        if filename is None:
            return
        if not (self.isRecording() or self.isPlaying()):
            self.fileEdit.setText(filename)

    @property
    def framenumber(self) -> int:
        '''Number of frames recorded, or the frame being shown.'''
        return self.slider.value()
