'''Still-frame capture from a live video stream.'''
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib.videotypes import Image
from QVideo.lib.imageops import stretch16, to8bit
from pathlib import Path
import numpy as np
import datetime
import logging


logger = logging.getLogger(__name__)

__all__ = ['QSnapshot']

#: The file types that hold 16 bit gray.
_DEEP_FORMATS = ('.png', '.tif', '.tiff')

try:
    _Fmt = QtGui.QImage.Format
except AttributeError:
    _Fmt = QtGui.QImage


class QSnapshot(QtCore.QObject):

    '''Save still frames from a live video stream.

    Connect any signal that emits an :class:`~QVideo.lib.videotypes.Image`
    (and, if it has one, the ``FrameInfo`` with its levels)
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
        Save the cached frame to a timestamped PNG in the home directory.
    snapAs()
        Prompt for a filename (pre-filled with the generated one), then save.
    '''

    def __init__(self, parent: QtWidgets.QWidget,
                 key: str = 'Ctrl+Shift+S',
                 key_as: str = 'Ctrl+Shift+Alt+S') -> None:
        super().__init__(parent)
        self._frame: Image | None = None
        #: The pixel values of the cached frame, if it has more than 8 bits,
        #: that are black and white: those of its ``FrameInfo``; ``None`` is
        #: the whole range.
        self.levels: tuple[float, float] | None = None
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(key), parent)
        shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.snap)
        shortcut_as = QtWidgets.QShortcut(QtGui.QKeySequence(key_as), parent)
        shortcut_as.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        shortcut_as.activated.connect(self.snapAs)

    @QtCore.Slot(np.ndarray, object)
    def newFrame(self, frame: Image, info: object = None) -> None:
        '''Cache the most recent frame, and the levels that it comes with.'''
        self._frame = frame
        self.levels = getattr(info, 'levels', None)

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
        '''Prompt for a filename, pre-filled, then save.'''
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
            Frame to save: ``uint8``, or ``uint16`` from a camera of more
            than 8 bits.
        filename : str
            Destination path.  The file format is inferred from the extension.

        Notes
        -----
        A gray ``uint16`` frame is saved with 16 bits to a PNG or TIFF
        file, stretched so that :attr:`levels` run from 0 to 65535 (a 12 bit
        image would look black otherwise).  Any other file, and a color
        frame, gets 8 bits between :attr:`levels`.
        '''
        deep = False
        if frame.dtype == np.uint16:
            deep = (frame.ndim == 2
                    and Path(filename).suffix.lower() in _DEEP_FORMATS)
            frame = (stretch16(frame, self.levels) if deep
                     else to8bit(frame, self.levels))
        elif frame.dtype != np.uint8:
            logger.warning(f'_save: unsupported dtype {frame.dtype}; '
                           'expected uint8 or uint16')
            return
        frame = np.ascontiguousarray(frame)
        if deep:
            h, w = frame.shape
            img = QtGui.QImage(frame.tobytes(), w, h, 2 * w,
                               _Fmt.Format_Grayscale16)
        elif frame.ndim == 2:
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
