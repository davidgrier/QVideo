'''Widget for saving the last N seconds of video to disk on demand.'''
from collections.abc import Callable
from pathlib import Path
from qtpy import QtCore, QtWidgets
import logging

from QVideo.lib.QVideoSource import QVideoSource
from .QCircularBuffer import QCircularBuffer
from . import formats


__all__ = ['QCircularDVRWidget']


logger = logging.getLogger(__name__)


class _Saver(QtCore.QThread):

    '''Runs the function ``job``, which writes a file, on a thread of its own.

    The result of the job is in :attr:`ok` when :attr:`finished` is emitted.
    '''

    def __init__(self, parent: QtCore.QObject) -> None:
        super().__init__(parent)
        self.job: Callable[[], bool] = lambda: False
        self.ok = False

    def run(self) -> None:
        self.ok = self.job()


class QCircularDVRWidget(QtWidgets.QWidget):

    '''Widget for saving the last N seconds of video to disk on demand.

    Connects to a :class:`~QVideo.lib.QVideoSource.QVideoSource` and
    continuously accumulates frames in a
    :class:`~QVideo.dvr.QCircularBuffer.QCircularBuffer`.  When the user
    clicks **Save**, the current buffer contents are written to disk in
    one batch.  The file format is determined by the filename extension,
    and the file is written by the same writers as
    :class:`~QVideo.dvr.QRecorder.QRecorder` uses (the table in
    :mod:`~QVideo.dvr.formats`), so every format that it supports is
    available, with PyAV for video files if that is installed.

    Unlike :class:`~QVideo.dvr.QDVRWidget.QDVRWidget` there is no
    *record* / *stop* cycle — the buffer is always accumulating.  This
    makes it easy to capture unexpected events retrospectively: set a
    duration, let the buffer fill, and click **Save** whenever something
    interesting happens.

    The file is written on a thread of its own, so a large buffer (high
    resolution or long duration) does not hold up the interface or the
    camera.  The **Save** button is disabled until the file is written, and
    the buffer goes on filling meanwhile; the frames that are saved are
    those that it held when **Save** was clicked.  Quitting the application
    waits for a save that is running.

    Parameters
    ----------
    source : QVideoSource or None
        Video source to connect.  May also be set later via
        :attr:`source`.
    parent : QWidget or None
        Parent widget.

    Signals
    -------
    saved(str)
        Emitted with the output filename after a successful save, when the
        file has been written.
    '''

    #: Emitted with the output filename after a successful save.
    saved = QtCore.Signal(str)

    FILENAME = 'circular.mkv'

    def __init__(self,
                 source: QVideoSource | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._buffer = QCircularBuffer()
        self._source: QVideoSource | None = None
        self._saver = _Saver(self)
        self._saving = ''
        self._setupUi()
        self._connectSignals()
        self.source = source
        saver = self._saver
        # Qt deletes children after it emits destroyed, so wait for a
        # save in progress here: a running thread must not be deleted
        self.destroyed.connect(lambda: saver.wait())
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(saver.wait)
            app.aboutToQuit.connect(self._buffer.clear)

    def _setupUi(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        dur_row = QtWidgets.QHBoxLayout()
        dur_row.addWidget(QtWidgets.QLabel('Duration:'))
        self._durationBox = QtWidgets.QSpinBox()
        self._durationBox.setRange(1, 300)
        self._durationBox.setValue(5)
        self._durationBox.setSuffix(' s')
        dur_row.addWidget(self._durationBox)
        dur_row.addStretch()
        layout.addLayout(dur_row)

        file_row = QtWidgets.QHBoxLayout()
        self._fileEdit = QtWidgets.QLineEdit(
            str(Path.home() / self.FILENAME))
        self._browseButton = QtWidgets.QPushButton('Browse…')
        file_row.addWidget(self._fileEdit)
        file_row.addWidget(self._browseButton)
        layout.addLayout(file_row)

        self._saveButton = QtWidgets.QPushButton('Save')
        self._saveButton.setEnabled(False)
        layout.addWidget(self._saveButton)

    def _connectSignals(self) -> None:
        self._durationBox.valueChanged.connect(self._setDuration)
        self._browseButton.clicked.connect(self._browse)
        self._saveButton.clicked.connect(self._save)
        self._saver.finished.connect(self._saved)

    @QtCore.Slot(int)
    def _setDuration(self, value: int) -> None:
        self._buffer.duration = value

    @QtCore.Slot()
    def _browse(self) -> None:
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save Circular Buffer',
            self._fileEdit.text(),
            formats.fileFilter(True),
            options=QtWidgets.QFileDialog.Option.DontUseNativeDialog)
        if filename:
            self._fileEdit.setText(filename)

    @QtCore.Slot()
    def _save(self) -> None:
        filename = self._fileEdit.text().strip()
        if not filename:
            self._browse()
            filename = self._fileEdit.text().strip()
        if not filename:
            return
        if self._saver.isRunning():
            return
        self._saveButton.setEnabled(False)
        self._saving = filename
        frames, fps = self._buffer.frames(), self._buffer.actualFps
        self._saver.job = lambda: self._write(filename, frames, fps)
        self._saver.start()

    @QtCore.Slot()
    def _saved(self) -> None:
        '''Report the result when the thread has written the file.'''
        self._saveButton.setEnabled(self._source is not None)
        if self._saver.ok:
            self.saved.emit(self._saving)
        else:
            logger.warning(f'Circular buffer save failed: {self._saving!r}')

    def _write(self, filename: str, frames: list, fps: float) -> bool:
        '''Write *frames* with the writer for the extension.

        This runs on the saving thread.  It returns ``False`` if there are
        no frames, the extension is not supported, or the writer gives up
        (the file cannot be created, or the frame size changed).
        '''
        if not frames:
            return False
        try:
            writer_class = formats.writerClass(filename)
        except ValueError as error:
            logger.error(error)
            return False
        writer = writer_class(filename, fps=fps, nframes=len(frames))
        failed = []
        writer.finished.connect(lambda: failed.append(True))
        for frame, info in frames:
            writer.write(frame, info)
            if failed:
                break
        writer.close()
        return not failed

    @property
    def source(self) -> QVideoSource | None:
        '''The connected :class:`~QVideo.lib.QVideoSource.QVideoSource`.'''
        return self._source

    @source.setter
    def source(self, source: QVideoSource | None) -> None:
        if self._source is not None:
            self._source.newFrame.disconnect(self._buffer.append)
        self._source = source
        if source is not None:
            if source.fps:
                self._buffer.fps = source.fps
            source.newFrame.connect(self._buffer.append)
        self._saveButton.setEnabled(source is not None)

    @property
    def buffer(self) -> QCircularBuffer:
        '''The underlying
        :class:`~QVideo.dvr.QCircularBuffer.QCircularBuffer`.'''
        return self._buffer
