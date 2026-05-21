'''Composite DVR widget for recording and playing back video streams.'''
from collections.abc import Callable
from qtpy import QtCore, QtGui, QtWidgets
from pathlib import Path
import numpy as np
from QVideo.lib import clickable, QVideoSource
from QVideo.lib.videotypes import Image
from .QOpenCVWriter import QOpenCVWriter
from .QOpenCVReader import QOpenCVSource

from .QHDF5Writer import QHDF5Writer
from .QHDF5Reader import QHDF5Source

try:
    import h5py as _h5py
    _h5py_available = True
except (ImportError, ModuleNotFoundError):
    _h5py_available = False
import logging


__all__ = ['QDVRWidget']


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
    '''

    #: Emitted for each frame during playback.
    newFrame = QtCore.Signal(np.ndarray)
    #: Emitted when recording starts (``True``) or stops (``False``).
    recording = QtCore.Signal(bool)
    #: Emitted when playback starts (``True``) or stops (``False``).
    playing = QtCore.Signal(bool)

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
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._source: QVideoSource | None = None
        self._writer: object | None = None
        self._player: QVideoSource | None = None
        self._thread: QtCore.QThread | None = None
        self._setupUi()
        self._connectSignals()
        self.source = source
        self.filename = filename if filename else str(
            Path.home() / self.FILENAME)

    def _setupUi(self) -> None:
        self.setFrameShape(QtWidgets.QFrame.Shape.Box)

        self.recordButton = QtWidgets.QPushButton('&Record', self)
        self.recordButton.setStatusTip('Record video')
        self.recordButton.setIcon(
            QtGui.QIcon(':/icons/icons/media-record.svg'))
        self.recordButton.setShortcut('R')

        self.stopButton = QtWidgets.QPushButton('&Stop', self)
        self.stopButton.setStatusTip('Stop recording')
        self.stopButton.setIcon(
            QtGui.QIcon(':/icons/icons/media-playback-stop.svg'))
        self.stopButton.setShortcut('S')

        self.frameNumber = QtWidgets.QLCDNumber(self)
        self.frameNumber.setSegmentStyle(
            QtWidgets.QLCDNumber.SegmentStyle.Flat)

        recordRow = QtWidgets.QHBoxLayout()
        recordRow.setSpacing(2)
        recordRow.setContentsMargins(0, 0, 6, 0)
        recordRow.addWidget(self.recordButton)
        recordRow.addWidget(self.stopButton)
        recordRow.addWidget(self.frameNumber)

        saveLabel = QtWidgets.QLabel('Save As', self)
        self.saveEdit = QtWidgets.QLineEdit(self)
        self.saveEdit.setReadOnly(True)
        self.saveEdit.setStatusTip('Video file name')
        saveLabel.setBuddy(self.saveEdit)

        saveRow = QtWidgets.QHBoxLayout()
        saveRow.setSpacing(6)
        saveRow.setContentsMargins(6, 0, 6, 0)
        saveRow.addWidget(saveLabel)
        saveRow.addWidget(self.saveEdit)

        self.rewindButton = QtWidgets.QPushButton('&Rewind', self)
        self.rewindButton.setStatusTip('Rewind video file')
        self.rewindButton.setIcon(
            QtGui.QIcon(':/icons/icons/media-skip-backward.svg'))

        self.pauseButton = QtWidgets.QPushButton('&Pause', self)
        self.pauseButton.setStatusTip('Pause video playback')
        self.pauseButton.setIcon(
            QtGui.QIcon(':/icons/icons/media-playback-pause.svg'))

        self.playButton = QtWidgets.QPushButton('P&lay', self)
        self.playButton.setStatusTip('Play video file')
        self.playButton.setIcon(
            QtGui.QIcon(':/icons/icons/media-playback-start.svg'))

        playRow = QtWidgets.QHBoxLayout()
        playRow.setSpacing(2)
        playRow.setContentsMargins(0, 1, 0, 1)
        playRow.addWidget(self.rewindButton)
        playRow.addWidget(self.pauseButton)
        playRow.addWidget(self.playButton)

        labelPlayFile = QtWidgets.QLabel('Play', self)
        self.playEdit = QtWidgets.QLineEdit(self)
        self.playEdit.setReadOnly(True)
        self.playEdit.setStatusTip('Video file')
        labelPlayFile.setBuddy(self.playEdit)

        playFileRow = QtWidgets.QHBoxLayout()
        playFileRow.setSpacing(6)
        playFileRow.setContentsMargins(6, 0, 6, 0)
        playFileRow.addWidget(labelPlayFile)
        playFileRow.addWidget(self.playEdit)

        labelNFrames = QtWidgets.QLabel('Duration', self)
        self.nframes = QtWidgets.QSpinBox(self)
        self.nframes.setToolTip('number of frames to record')
        self.nframes.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight)
        self.nframes.setRange(10, 99000)
        self.nframes.setSingleStep(10)
        self.nframes.setValue(10000)
        labelNFrames.setBuddy(self.nframes)

        labelInterval = QtWidgets.QLabel('Interval', self)
        self.nskip = QtWidgets.QSpinBox(self)
        self.nskip.setToolTip('Record every Nth frame')
        self.nskip.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight)
        self.nskip.setRange(1, 999)
        labelInterval.setBuddy(self.nskip)

        framesRow = QtWidgets.QHBoxLayout()
        framesRow.setSpacing(6)
        framesRow.setContentsMargins(6, 4, 6, 4)
        framesRow.addWidget(labelNFrames)
        framesRow.addWidget(self.nframes)
        framesRow.addWidget(labelInterval)
        framesRow.addWidget(self.nskip)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(recordRow)
        layout.addLayout(saveRow)
        layout.addLayout(playRow)
        layout.addLayout(playFileRow)
        layout.addLayout(framesRow)

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
        try:
            options = QtWidgets.QFileDialog.Option.DontUseNativeDialog
        except AttributeError:
            options = QtWidgets.QFileDialog.DontUseNativeDialog
        filename, _ = get(self, 'Video File Name',
                          str(self.filename),
                          self._buildFilter(save),
                          options=options)
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
        writer_class = self.Writer[suffix]
        self._writer = writer_class(self.filename,
                                    fps=self.source.fps,
                                    nframes=self.nframes.value(),
                                    nskip=self.nskip.value())
        self._writer.frameNumber.connect(self.setFrameNumber)
        self._writer.finished.connect(self.stop)
        self._thread = QtCore.QThread()
        self._writer.moveToThread(self._thread)
        self._thread.start()
        self.source.newFrame.connect(self._writer.write)
        self.recording.emit(True)

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
        if self.isRecording():
            logger.debug('Stopping Recording')
            try:
                self.source.newFrame.disconnect(self._writer.write)
                self._writer.frameNumber.disconnect(self.setFrameNumber)
                self._writer.finished.disconnect(self.stop)
            except (RuntimeError, TypeError):
                logger.debug(
                    'Some recording signals were already disconnected')
            self._thread.quit()
            self._thread.wait()
            self._writer.close()
            self._thread = None
            self._writer = None
            self.recording.emit(False)
        if self.isPlaying():
            logger.debug('Stopping Playback')
            try:
                self._player.newFrame.disconnect(self.stepFrameNumber)
                self._player.newFrame.disconnect(self.newFrame)
            except (RuntimeError, TypeError):
                logger.debug('Playback signal was already disconnected')
            self._player.stop()
            self._player = None
            self.playing.emit(False)
        self.framenumber = 0

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop recording or playback when the widget is closed.'''
        self.stop()
        super().closeEvent(event)

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
