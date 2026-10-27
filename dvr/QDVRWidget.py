'''Composite DVR widget for recording and playing back video streams.'''
import functools
import os
from qtpy import QtCore, QtGui, QtWidgets
from pathlib import Path
import numpy as np
from QVideo.lib import clickable, QVideoSource
from . import formats
from .QRecorder import QRecorder
from .QPlayer import QPlayer

import logging


__all__ = ['QDVRWidget']


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

    The controls of a :class:`~QVideo.dvr.QRecorder.QRecorder`
    (:attr:`recorder`), which
    captures the frames of a
    :class:`~QVideo.lib.QVideoSource.QVideoSource` to a file, and of a
    :class:`~QVideo.dvr.QPlayer.QPlayer` (:attr:`playback`), which plays
    recorded files.
    The widget asks the user for file names and confirms what could do
    harm; the recorder and the player do the work, and are available to
    applications without a window.  Supported formats are those of
    :mod:`~QVideo.dvr.formats`: AVI (``.avi``), MKV (``.mkv``), and MP4
    (``.mp4``) by PyAV if it is installed and by OpenCV if not; HDF5
    (``.h5``) when ``h5py`` is installed.  Requesting an unsupported
    extension is logged as an error and silently ignored.

    Recording and playback stop automatically when the widget is closed
    or the application is about to quit.

    Parameters
    ----------
    source : QVideoSource or None
        Video source supplying frames to record.
    filename : str or None
        Default file path for saving.  If ``None``, defaults to
        ``~/default.mkv``.
    stopWhenBehind, lagLimit, maxMemory :
        Passed to the :class:`~QVideo.dvr.QRecorder.QRecorder`, which
        explains them and which is available as :attr:`recorder`.
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
    so no recorded frame is lost.
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

    FILENAME = 'default.mkv'

    def __init__(self,
                 *args,
                 source: QVideoSource | None = None,
                 filename: str = '',
                 stopWhenBehind: bool = True,
                 lagLimit: float = 1.,
                 maxMemory: float | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        #: The recorder that this widget controls.
        self.recorder = QRecorder(stopWhenBehind=stopWhenBehind,
                                  lagLimit=lagLimit, maxMemory=maxMemory,
                                  parent=self)
        #: The player that this widget controls.
        self.playback = QPlayer(self)
        self._source: QVideoSource | None = None
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
        recorder, player = self.recorder, self.playback
        recorder.recording.connect(self.recording)
        recorder.recording.connect(self._update)
        recorder.frameNumber.connect(self._setFrameNumber)
        recorder.backlog.connect(self.backlog)
        recorder.behind.connect(self.behind)
        recorder.stopped.connect(self.stopped)
        player.playing.connect(self.playing)
        player.playing.connect(self._update)
        player.newFrame.connect(self.newFrame)
        player.positionChanged.connect(self._follow)
        player.ended.connect(self._updateUi)

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

    @QtCore.Slot(bool)
    def _update(self, on: bool) -> None:
        '''Show the controls for a recording or video that has started or
        stopped, and clear the read-outs when one has stopped.'''
        if not on:
            self._display(0, 0, 1.)
        self._updateUi()

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
        return self.recorder.isRecording()

    def isPlaying(self) -> bool:
        '''Return ``True`` if playback is in progress.'''
        return self.playback.isPlaying()

    def isPaused(self) -> bool:
        '''Return ``True`` if playback is paused.'''
        return self.playback.isPaused()

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
        dialog.setNameFilter(formats.fileFilter(True))
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
        if not (self._accepts(formats.Writer) and self._mayRecord()):
            return
        logger.debug(f'Recording: {self.filename}')
        self.recorder.start(self.filename, self.nframes.value(),
                            self.nskip.value(), overwrite=True)
        self._display(0, self.recorder.nframes, self.recorder.rate)

    def _accepts(self, table: dict[str, type]) -> bool:
        '''Return whether the file name has an extension of *table*.

        Asks for a file name if there is none, and logs an extension that
        the table does not have.
        '''
        if not (self.filename or self.getFileName()):
            return False
        suffix = Path(self.filename).suffix
        if suffix not in table:
            logger.error(f'Unsupported file format: {suffix!r}')
        return suffix in table

    @QtCore.Slot()
    def play(self) -> None:
        '''Start playback, or resume if paused.

        Does nothing if recording is active or playback is already
        running.  Warns, and does not play, if the file does not exist.
        A paused video that has reached its end starts over.
        '''
        if self.isPaused():
            self.playback.resume()
            self._updateUi()
            return
        if self.isRecording() or self.isPlaying():
            return
        if not self._accepts(formats.Reader):
            return
        if not Path(self.filename).is_file():
            self._warn(f'There is no file {Path(self.filename).name} '
                       'to play.')
            return
        logger.debug(f'Starting Playback: {self.filename}')
        try:
            self.playback.start(self.filename)
        except OSError:
            pass  # the reader has said why

    @QtCore.Slot()
    def pause(self) -> None:
        '''Pause playback.  :meth:`play` resumes it.'''
        self.playback.pause()
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
        self.playback.seek(framenumber)

    @QtCore.Slot()
    def rewind(self) -> None:
        '''Go to the first frame and pause.'''
        self.playback.rewind()
        self._updateUi()

    def step(self, frames: int = 1) -> None:
        '''Pause and move *frames* frames forward, or back if negative.'''
        self.playback.step(frames)
        self._updateUi()

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop recording or playback.'''
        self.recorder.stop()
        self.playback.stop()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop recording or playback when the widget is closed.'''
        self.stop()
        super().closeEvent(event)

    @QtCore.Slot(int)
    def _setFrameNumber(self, framenumber: int) -> None:
        '''Show that *framenumber* frames have been recorded.'''
        if self.isRecording():  # one may arrive after the recording stops
            self._display(framenumber, self.recorder.nframes,
                          self.recorder.rate)

    @QtCore.Slot(int)
    def _follow(self, done: int) -> None:
        '''Show that *done* frames of the video have been played.'''
        player = self.playback
        self._display(done, max(player.length, done), player.fps)

    @property
    def source(self) -> QVideoSource | None:
        '''The :class:`~QVideo.lib.QVideoSource.QVideoSource` being
        recorded.  Without one (``None``) the record button is disabled.'''
        return self._source

    @source.setter
    def source(self, source: QVideoSource | None) -> None:
        logger.debug(f'Setting source {type(source)}')
        self._source = source
        self.recorder.source = source
        self._updateUi()

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
