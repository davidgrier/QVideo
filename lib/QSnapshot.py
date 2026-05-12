'''Still-frame capture from a live video stream.'''
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib.videotypes import Image
from pathlib import Path
import numpy as np
import datetime
import logging


logger = logging.getLogger(__name__)

__all__ = ['QSnapshot']

try:
    _Fmt = QtGui.QImage.Format
except AttributeError:
    _Fmt = QtGui.QImage


class QSnapshot(QtCore.QObject):

    '''Save still frames from a live video stream.

    Connect any signal that emits an :class:`~QVideo.lib.videotypes.Image`
    to :meth:`newFrame` so that the most recent frame is always cached.
    Call :meth:`snap` (or press the hotkey) to write the cached frame to disk.
    Call :meth:`snapAs` to choose the save path via a file dialog.

    The source determines what is captured:

    - ``QVideoSource.newFrame`` — raw camera frames, no filters
    - ``QVideoScreen.newFrame`` — post-filter frames
    - ``QVideoScreen.newFrame`` with ``composite=True`` — filtered + overlaid

    Frames are saved as-is; no channel reordering is applied.  For cameras
    that deliver BGR data (e.g. OpenCV), the saved PNG will have swapped
    red and blue channels compared to the on-screen display.

    Parameters
    ----------
    parent : QWidget
        Parent widget.  Shortcuts are registered on this widget.
    key : str
        Keyboard shortcut that triggers :meth:`snap` (auto-timestamp save).
        Default: ``'Ctrl+Shift+S'``.
    key_as : str
        Keyboard shortcut that triggers :meth:`snapAs` (file-dialog save).
        Default: ``'Ctrl+Shift+Alt+S'``.

    Slots
    -----
    newFrame(Image)
        Cache the most recent frame.
    snap()
        Save the cached frame to a timestamped PNG in the user's home directory.
    snapAs()
        Prompt for a filename pre-filled with the auto-generated name, then save.
    '''

    def __init__(self, parent: QtWidgets.QWidget,
                 key: str = 'Ctrl+Shift+S',
                 key_as: str = 'Ctrl+Shift+Alt+S') -> None:
        super().__init__(parent)
        self._frame: Image | None = None
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(key), parent)
        shortcut.activated.connect(self.snap)
        shortcut_as = QtWidgets.QShortcut(QtGui.QKeySequence(key_as), parent)
        shortcut_as.activated.connect(self.snapAs)

    @QtCore.Slot(np.ndarray)
    def newFrame(self, frame: Image) -> None:
        '''Cache the most recent frame.'''
        self._frame = frame

    def _defaultPath(self) -> str:
        '''Return a timestamped PNG path in the user's home directory.'''
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        return str(Path.home() / f'snapshot_{timestamp}.png')

    @QtCore.Slot()
    def snap(self) -> None:
        '''Save the cached frame to a timestamped PNG in the home directory.'''
        if self._frame is None:
            logger.warning('snap: no frame available')
            return
        self._save(self._frame, self._defaultPath())

    @QtCore.Slot()
    def snapAs(self) -> None:
        '''Prompt for a filename pre-filled with the auto-generated name, then save.'''
        if self._frame is None:
            logger.warning('snapAs: no frame available')
            return
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            None, 'Save Snapshot', self._defaultPath(),
            'PNG Images (*.png);;TIFF Images (*.tiff);;JPEG Images (*.jpg)')
        if filename:
            self._save(self._frame, filename)

    def _save(self, frame: Image, filename: str) -> None:
        '''Write *frame* to *filename* using Qt image facilities.

        Parameters
        ----------
        frame : Image
            Frame to save.  Must be uint8.
        filename : str
            Destination path.  The file format is inferred from the extension.
        '''
        if frame.dtype != np.uint8:
            logger.warning(f'_save: unsupported dtype {frame.dtype}; '
                           'expected uint8')
            return
        frame = np.ascontiguousarray(frame)
        if frame.ndim == 2:
            h, w = frame.shape
            img = QtGui.QImage(frame.tobytes(), w, h, w,
                               _Fmt.Format_Grayscale8)
        elif frame.ndim == 3 and frame.shape[2] == 3:
            h, w = frame.shape[:2]
            img = QtGui.QImage(frame.tobytes(), w, h, 3 * w,
                               _Fmt.Format_RGB888)
        elif frame.ndim == 3 and frame.shape[2] == 4:
            h, w = frame.shape[:2]
            img = QtGui.QImage(frame.tobytes(), w, h, 4 * w,
                               _Fmt.Format_RGBA8888)
        else:
            logger.warning(f'_save: unsupported frame shape {frame.shape}')
            return
        if not img.save(filename):
            logger.warning(f'_save: failed to save {filename!r}')
        else:
            logger.info(f'Snapshot saved: {filename!r}')

    @classmethod
    def example(cls: type['QSnapshot']) -> None:  # pragma: no cover
        '''Demonstrate QSnapshot with a noise source.'''
        import pyqtgraph as pg
        from QVideo.cameras.Noise import QNoiseSource

        app = pg.mkQApp()
        window = QtWidgets.QWidget()
        snapshot = cls(window)
        source = QNoiseSource()
        source.newFrame.connect(snapshot.newFrame)
        source.start()
        window.show()
        pg.exec()


if __name__ == '__main__':  # pragma: no cover
    QSnapshot.example()
