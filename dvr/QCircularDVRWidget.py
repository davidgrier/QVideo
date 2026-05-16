'''Widget for saving the last N seconds of video to disk on demand.'''
from pathlib import Path
from qtpy import QtCore, QtWidgets
import logging

from QVideo.lib.QVideoSource import QVideoSource
from .QCircularBuffer import QCircularBuffer
from .QDVRWidget import QDVRWidget


__all__ = ['QCircularDVRWidget']


logger = logging.getLogger(__name__)


class QCircularDVRWidget(QtWidgets.QWidget):

    '''Widget for saving the last N seconds of video to disk on demand.

    Connects to a :class:`~QVideo.lib.QVideoSource.QVideoSource` and
    continuously accumulates frames in a
    :class:`~QVideo.dvr.QCircularBuffer.QCircularBuffer`.  When the user
    clicks **Save**, the current buffer contents are written to disk in
    one batch.  The file format is determined by the filename extension;
    all formats supported by :class:`~QVideo.dvr.QDVRWidget.QDVRWidget`
    are available.

    Unlike :class:`~QVideo.dvr.QDVRWidget.QDVRWidget` there is no
    *record* / *stop* cycle — the buffer is always accumulating.  This
    makes it easy to capture unexpected events retrospectively: set a
    duration, let the buffer fill, and click **Save** whenever something
    interesting happens.

    The save operation runs on the main thread; for very large buffers
    (high resolution or long duration) there will be a brief pause.

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
        Emitted with the output filename after a successful save.
    '''

    #: Emitted with the output filename after a successful save.
    saved = QtCore.Signal(str)

    FILENAME = 'circular.mkv'

    def __init__(self,
                 source: 'QVideoSource | None' = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._buffer = QCircularBuffer()
        self._source: 'QVideoSource | None' = None
        self._setupUi()
        self._connectSignals()
        if source is not None:
            self.source = source
        app = QtCore.QCoreApplication.instance()
        if app is not None:
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

    @QtCore.Slot(int)
    def _setDuration(self, value: int) -> None:
        self._buffer.duration = value

    @QtCore.Slot()
    def _browse(self) -> None:
        try:
            options = QtWidgets.QFileDialog.Option.DontUseNativeDialog
        except AttributeError:
            options = QtWidgets.QFileDialog.DontUseNativeDialog
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save Circular Buffer',
            self._fileEdit.text(),
            QDVRWidget._buildFilter(True),
            options=options)
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
        self._saveButton.setEnabled(False)
        success = self._buffer.save(filename)
        self._saveButton.setEnabled(True)
        if success:
            self.saved.emit(filename)
        else:
            logger.warning(f'Circular buffer save failed: {filename!r}')

    @property
    def source(self) -> 'QVideoSource | None':
        '''The connected :class:`~QVideo.lib.QVideoSource.QVideoSource`.'''
        return self._source

    @source.setter
    def source(self, source: 'QVideoSource | None') -> None:
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
        '''The underlying :class:`~QVideo.dvr.QCircularBuffer.QCircularBuffer`.'''
        return self._buffer
