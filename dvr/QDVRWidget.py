from pyqtgraph.Qt import QtCore, QtGui, QtWidgets, uic
from pathlib import Path
from QVideo.lib import clickable, QVideoSource
from .QAVIWriter import QAVIWriter
from .QMKVWriter import QMKVWriter
from .QMP4Writer import QMP4Writer
from .QAVIReader import QAVISource
from .QHDF5Writer import QHDF5Writer
from .QHDF5Reader import QHDF5Source
import logging


__all__ = ['QDVRWidget']


logger = logging.getLogger(__name__)

try:
    from .icons_rc import *
except Exception:
    logger.debug('Could not load DVR icons; buttons will show text labels only')


class QDVRWidget(QtWidgets.QFrame):

    '''Widget providing record, play, pause, stop and rewind controls
    for a digital video recorder.

    Connects to a :class:`~QVideo.lib.QVideoSource.QVideoSource` to
    capture incoming frames to a file, and can play back previously
    recorded files.  Supported formats are determined by the
    :attr:`Writer` and :attr:`Player` class attributes; by default
    AVI (``.avi``), MKV (``.mkv``), MP4 (``.mp4``), and HDF5 (``.h5``) are supported.  Requesting an
    unsupported extension is logged as an error and silently ignored.

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
        Forwarded to :class:`~pyqtgraph.Qt.QtWidgets.QFrame`.
    **kwargs :
        Forwarded to :class:`~pyqtgraph.Qt.QtWidgets.QFrame`.

    Signals
    -------
    recording(bool)
        Emitted when recording starts (``True``) or stops (``False``).
    playing(bool)
        Emitted when playback starts (``True``) or stops (``False``).
    '''

    recording = QtCore.pyqtSignal(bool)
    playing = QtCore.pyqtSignal(bool)

    UIFILE = Path(__file__).parent / 'QDVRWidget.ui'
    FILENAME = 'default.mkv'

    GetFileName = {True: QtWidgets.QFileDialog.getSaveFileName,
                   False: QtWidgets.QFileDialog.getOpenFileName}

    Writer = {'.avi': QAVIWriter,
              '.mkv': QMKVWriter,
              '.mp4': QMP4Writer,
              '.h5': QHDF5Writer}
    Player = {'.avi': QAVISource,
              '.mkv': QAVISource,
              '.mp4': QAVISource,
              '.h5': QHDF5Source}

    FileGroups = {'Video files': {'.avi', '.mkv', '.mp4'},
                  'HDF5 files': {'.h5'}}

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
        for label, exts in cls.FileGroups.items():
            matching = sorted(exts & formats)
            if matching:
                parts.append(
                    f'{label} ({" ".join("*" + e for e in matching)})')
        return ';;'.join(parts) if parts else 'All files (*)'

    def __init__(self,
                 *args,
                 source: QVideoSource | None = None,
                 filename: str | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._source = None
        self._writer = None
        self._player = None
        self._thread = None
        self._setupUi()
        self._connectSignals()
        self.source = source
        self.filename = filename if filename is not None else str(
            Path.home() / self.FILENAME)

    def _setupUi(self) -> None:
        uic.loadUi(self.UIFILE, self)
        self._framenumber = 0

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
        if self.isPlaying():
            return self._player.isPaused()
        return False

    def getFileName(self, save: bool = False) -> str:
        '''Open a file dialog and update the filename fields.

        Parameters
        ----------
        save : bool
            If ``True``, open a save dialog; otherwise open an open dialog.

        Returns
        -------
        str
            Selected filename, or empty string if cancelled.
        '''
        if self.isPlaying() or self.isRecording():
            return ''
        get = self.GetFileName[save]
        filename, _ = get(self, 'Video File Name',
                          str(self.filename),
                          self._buildFilter(save))
        if filename:
            self.playname = filename
            if save:
                self.filename = filename
        return filename

    @QtCore.pyqtSlot()
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
        self._thread.finished.connect(self._writer.close)
        self._writer.moveToThread(self._thread)
        self._thread.start()
        self.source.newFrame.connect(self._writer.write)
        self.recording.emit(True)

    @QtCore.pyqtSlot()
    def play(self) -> None:
        '''Start playback, or resume if paused.

        Does nothing if recording is active, if playback is already
        running, or if the playback filename has an unsupported extension.
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
            self.playing.emit(True)
            self._player.start()
        else:
            self._player = None

    @QtCore.pyqtSlot()
    def pause(self) -> None:
        '''Pause or resume playback.'''
        if self.isPlaying():
            if self._player.isPaused():
                self._player.resume()
            else:
                self._player.pause()

    @QtCore.pyqtSlot()
    def rewind(self) -> None:
        '''Rewind to the first frame and pause.'''
        if self.isPlaying():
            self._player.source.rewind()
            self._player.pause()
            self.framenumber = 0

    @QtCore.pyqtSlot()
    def stop(self) -> None:
        '''Stop recording or playback.'''
        if self.isRecording():
            logger.debug('Stopping Recording')
            self.source.newFrame.disconnect(self._writer.write)
            self._writer.frameNumber.disconnect(self.setFrameNumber)
            self._writer.finished.disconnect(self.stop)
            self._thread.finished.disconnect(self._writer.close)
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._writer = None
            self.recording.emit(False)
        if self.isPlaying():
            logger.debug('Stopping Playback')
            self._player.newFrame.disconnect(self.stepFrameNumber)
            self._player.stop()
            self._player = None
            self.playing.emit(False)
        self.framenumber = 0

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop recording or playback when the widget is closed.'''
        self.stop()
        super().closeEvent(event)

    @QtCore.pyqtSlot(int)
    def setFrameNumber(self, framenumber: int) -> None:
        '''Set the displayed frame number.'''
        self.framenumber = framenumber

    @QtCore.pyqtSlot()
    def stepFrameNumber(self) -> None:
        '''Increment the displayed frame number.'''
        self.framenumber += 1

    @QtCore.pyqtProperty(QVideoSource)
    def source(self) -> QVideoSource:
        '''The :class:`~QVideo.lib.QVideoSource.QVideoSource` being recorded.'''
        return self._source

    @source.setter
    def source(self, source: QVideoSource | None) -> None:
        '''Set the video source.  Disables the record button when ``None``.'''
        logger.debug(f'Setting source {type(source)}')
        self._source = source
        self.recordButton.setDisabled(source is None)

    @QtCore.pyqtProperty(str)
    def filename(self) -> str:
        '''Current save filename.'''
        return str(self.saveEdit.text())

    @filename.setter
    def filename(self, filename: str | None) -> None:
        if filename is None:
            return
        if not (self.isRecording() or self.isPlaying()):
            self.saveEdit.setText(filename)
            self.playname = self.filename

    @QtCore.pyqtProperty(str)
    def playname(self) -> str:
        '''Current playback filename.'''
        return str(self.playEdit.text())

    @playname.setter
    def playname(self, filename: str) -> None:
        if not self.isPlaying():
            self.playEdit.setText(filename)

    @QtCore.pyqtProperty(int)
    def framenumber(self) -> int:
        '''Current frame number displayed in the LCD.'''
        return self._framenumber

    @framenumber.setter
    def framenumber(self, number: int) -> None:
        self._framenumber = number
        self.frameNumber.display(self._framenumber)
