'''Still-frame capture from a live video stream.'''
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib.videotypes import Image
from QVideo.lib.QImageSaver import QImageSaver
from QVideo.lib.QVideoScreen import QVideoScreen
from pathlib import Path
import numpy as np
import logging


logger = logging.getLogger(__name__)

__all__ = ['QSnapshot']


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

    With a *screen*, the same object also saves what the screen shows
    (:meth:`screenshot` and :meth:`screenshotAs`): the video with its
    filters, color map and overlays, as an 8 bit color PNG whatever the
    depth of the camera.  :meth:`snap` saves the data and :meth:`screenshot`
    the display.

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
    screen : QVideoScreen, optional
        The screen that :meth:`screenshot` captures.  Without one, the
        screenshot shortcuts are not registered.
    key_screen : str
        Keyboard shortcut for :meth:`screenshot`.
        Default: ``'Ctrl+Shift+P'``.
    key_screen_as : str
        Keyboard shortcut for :meth:`screenshotAs`.
        Default: ``'Ctrl+Shift+Alt+P'``.

    The directory of the last file is remembered from session to session
    (see :class:`~QVideo.lib.QImageSaver.QImageSaver`).  The file is
    written by :attr:`saver`, a
    :class:`~QVideo.lib.QImageSaver.QImageSaver`, whose ``message`` signal
    reports each outcome.

    Slots
    -----
    newFrame(Image)
        Cache the most recent frame.
    snap()
        Save the cached frame to a timestamped PNG in the home directory.
    snapAs()
        Prompt for a filename (pre-filled with the generated one), then save.
    screenshot()
        Save what the screen shows to a timestamped PNG.
    screenshotAs()
        Prompt for a filename, then save what the screen shows.
    '''

    def __init__(self, parent: QtWidgets.QWidget,
                 key: str = 'Ctrl+Shift+S',
                 key_as: str = 'Ctrl+Shift+Alt+S',
                 screen: QVideoScreen | None = None,
                 key_screen: str = 'Ctrl+Shift+P',
                 key_screen_as: str = 'Ctrl+Shift+Alt+P') -> None:
        super().__init__(parent)
        #: The screen whose display :meth:`screenshot` saves, if any.
        self.screen = screen
        self._frame: Image | None = None
        #: The pixel values of the cached frame, if it has more than 8 bits,
        #: that are black and white: those of its ``FrameInfo``; ``None`` is
        #: the whole range.
        self.levels: tuple[float, float] | None = None
        #: Writes the files and reports the outcome (``saver.message``).
        self.saver = QImageSaver(self, Path.home(), 'snapshot',
                                 title='Save Snapshot', key='images')
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(key), parent)
        shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.snap)
        shortcut_as = QtWidgets.QShortcut(QtGui.QKeySequence(key_as), parent)
        shortcut_as.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut_as.activated.connect(self.snapAs)
        if screen is not None:
            for sequence, slot in ((key_screen, self.screenshot),
                                   (key_screen_as, self.screenshotAs)):
                shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(sequence),
                                               parent)
                shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
                shortcut.activated.connect(slot)

    @QtCore.Slot(np.ndarray, object)
    def newFrame(self, frame: Image, info: object = None) -> None:
        '''Cache the most recent frame, and the levels that it comes with.'''
        self._frame = frame
        self.levels = getattr(info, 'levels', None)

    @QtCore.Slot()
    def snap(self) -> None:
        '''Save the cached frame to a timestamped PNG in the home directory.'''
        if self._frame is None:
            logger.warning('snap: no frame available')
            return
        self.saver.save(self._frame, levels=self.levels)

    @QtCore.Slot()
    def snapAs(self) -> None:
        '''Prompt for a filename, pre-filled, then save.'''
        if self._frame is None:
            logger.warning('snapAs: no frame available')
            return
        self.saver.save(self._frame, ask=True, levels=self.levels)

    @QtCore.Slot()
    def screenshot(self) -> None:
        '''Save what the screen shows to a timestamped PNG.'''
        self._screenshot(ask=False)

    @QtCore.Slot()
    def screenshotAs(self) -> None:
        '''Prompt for a filename, pre-filled, then save the screenshot.'''
        self._screenshot(ask=True)

    def _screenshot(self, ask: bool) -> None:
        if self.screen is None:
            logger.warning('screenshot: no screen')
            return
        image = self.screen.screenshot()
        if image.size == 0:
            logger.warning('screenshot: the screen has no size')
            return
        self.saver.save(image, ask=ask, prefix='screenshot')
