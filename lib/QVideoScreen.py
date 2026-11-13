'''Live video display widget with mouse-aware graphical overlay support.'''
import logging
from typing import Any, cast

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from pyqtgraph import GraphicsLayoutWidget, ImageItem

from QVideo.lib.QVideoSource import QVideoSource
from QVideo.lib.QFrameRelay import QFrameRelay
from QVideo.lib.videotypes import FrameInfo, Image
from QVideo.lib.imageops import AutoLevels, ImageFormat


logger = logging.getLogger(__name__)

#: The time [ms] that the shape must rest before the window is fitted to it.
_FIT_DELAY = 300

__all__ = ['QVideoScreen']


#: Frames between the estimates of the levels of ``autoLevels``.
_AUTO_EVERY = 5


class QVideoScreen(GraphicsLayoutWidget):

    '''Video display widget.

    Displays frames from a :class:`~QVideo.lib.QVideoSource` in real time,
    with optional frame-rate throttling.  The screen applies no filters;
    to display filtered frames, make a
    :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` its source.

    Inherits from :class:`pyqtgraph.GraphicsLayoutWidget`.

    Parameters
    ----------
    size : tuple[int, int]
        Initial widget dimensions in pixels. Default: ``(640, 480)``.
    framerate : int | None
        Maximum display frame rate in frames per second.
        ``None`` means no throttling. Default: ``None``.
    *args :
        Forwarded to :class:`pyqtgraph.GraphicsLayoutWidget`.
    **kwargs :
        Forwarded to :class:`pyqtgraph.GraphicsLayoutWidget`.

    Properties
    ----------
    framerate : int | None
        Maximum display frame rate [fps]. Setting this updates the throttle
        interval.
    source : QVideoSource
        The video source. Setting this connects the source to the display.
    fps : float | None
        Frame rate of the connected source [fps]. ``None`` when no source
        is connected. Read-only.
    composite : bool
        Controls what :attr:`newFrame` emits.  When ``False`` (default),
        :attr:`newFrame` carries the displayed video frame.  When ``True``,
        it carries the rendered scene (video + overlays) as an
        ``(H, W, 3)`` RGB uint8 array.
    colormap : str | None
        Colormap name for false-color display of grayscale frames.
        Accepts any matplotlib colormap name (e.g. ``'inferno'``,
        ``'viridis'``) or a pyqtgraph built-in name.
        Set to ``None`` (default) to display in grayscale.
        Has no effect on color (3-channel) frames.
    levels : tuple[float, float] | None
        The values that the display shows as black and as white.  ``None``
        (default) maps the whole range of the type of the frame, 0 to 255
        for ``uint8`` and 0 to 65535 for ``uint16``, so a 12 bit frame in
        ``uint16`` looks 16 times too dark until ``levels`` is
        ``(0, 4095)``.

    autoLevels : tuple[float, float] | None
        Percentiles of the frame that the display shows as black and as
        white, for example ``(1, 99)``, so that a dim or low contrast
        frame fills the screen.  ``None`` (default) is off.  Explicit
        :attr:`levels` win.  The data are not changed.

    Signals
    -------
    newFrame(numpy.ndarray, FrameInfo)
        Emitted after each displayed frame.  Carries either the video
        frame or the rendered composite scene, depending on
        :attr:`composite`, and the
        :class:`~QVideo.lib.videotypes.FrameInfo` of the frame that was
        displayed (``None`` if the source provided none).
    '''

    #: Emitted after each displayed frame with the frame and its info.
    newFrame = QtCore.Signal(np.ndarray, object)

    def __init__(self, *args,
                 size: tuple[int, int] = (640, 480),
                 framerate: int | None = None,
                 **kwargs) -> None:
        super().__init__(*args, size=size, **kwargs)
        self.framerate = framerate
        self._colormap: str | None = None
        self._levels: tuple[float, float] | None = None
        self._shownLevels: tuple[float, float] | None = None
        self._auto: AutoLevels | None = None
        self._ready = True
        self._pending: tuple[Image, FrameInfo | None] | None = None
        self._overlays: list[QtWidgets.QGraphicsItem] = []
        self._composite = False
        self._videoShape: QtCore.QSize | None = None
        self._source: QVideoSource | None = None
        self._relay: QFrameRelay | None = None
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._setready)
        self._fitTimer = QtCore.QTimer(self)
        self._fitTimer.setSingleShot(True)
        self._fitTimer.setInterval(_FIT_DELAY)
        self._fitTimer.timeout.connect(self._fitToVideo)
        self._setupUi()

    def _setupUi(self) -> None:
        '''Make the view, which keeps the aspect ratio, and the image.'''
        self.ci.layout.setContentsMargins(  # pyright: ignore[reportAttributeAccessIssue]
            0, 0, 0, 0)
        self.view = self.addViewBox(  # pyright: ignore[reportAttributeAccessIssue]
            enableMenu=False, enableMouse=False)
        self.view.invertY(True)
        self.view.setAspectLocked(True)
        self.view.setDefaultPadding(0)
        self._showAll(self.width(), self.height())
        self.image = ImageItem(axisOrder='row-major')
        self.view.addItem(self.image)

    @property
    def source(self) -> QVideoSource | None:
        '''The video source providing frames to display.'''
        return self._source

    @source.setter
    def source(self, source: QVideoSource | None) -> None:
        if self._source is not None:
            self._source.shapeChanged.disconnect(self.updateShape)
        self._source = source
        self._relay = None
        self._fitTimer.stop()
        if source is None:
            return
        self._videoShape = None     # a new source fits the window at once
        self.updateShape(source.shape)
        source.shapeChanged.connect(self.updateShape)
        self._relay = QFrameRelay(source)
        self._relay.newFrame.connect(self.setImage)

    @property
    def framerate(self) -> int | None:
        '''Maximum display frame rate [fps].

        Accommodate high-speed cameras by throttling the rate at
        which frames are displayed. ``None`` for no throttling.'''
        return self._framerate

    @framerate.setter
    def framerate(self, framerate: int | None) -> None:
        if framerate is not None and framerate <= 0:
            raise ValueError('framerate must be positive, '
                             f'got {framerate}')
        self._framerate = framerate
        self._interval = 0 if framerate is None else int(1000 / framerate)

    @property
    def colormap(self) -> str | None:
        '''Colormap name for false-color display of grayscale frames.

        Set to a colormap name (matplotlib or pyqtgraph built-in) to
        apply false-color mapping. Set to ``None`` to restore grayscale.
        Has no effect on color (3-channel) frames.
        '''
        return self._colormap

    @colormap.setter
    def colormap(self, name: str | None) -> None:
        if name is None:
            self.image.setLookupTable(None)
        else:
            try:
                colormap = pg.colormap.get(name, source='matplotlib')
            except (KeyError, FileNotFoundError, ImportError):
                colormap = pg.colormap.get(name)
            self.image.setColorMap(cast(pg.ColorMap, colormap))
        self._colormap = name       # only once the colormap is in use

    @property
    def levels(self) -> tuple[float, float] | None:
        '''The values that the display shows as black and as white.

        Setting levels fixes them for every frame that follows, gray or
        color, until they are changed: ``(0, 4095)`` shows the counts of a
        12 bit camera.  Setting ``None`` (the default) lets each frame bring
        its own, in the :class:`~QVideo.lib.videotypes.FrameInfo` that
        accompanies it (a deep camera sends its counts and their range);
        a frame without levels fills the range of its type (0 to 255 for
        ``uint8``, 0 to 65535 for ``uint16``).  The property reads the
        levels that the display uses now.

        Raises
        ------
        ValueError
            If the white level is not above the black level.
        '''
        levels = cast('tuple[float, float] | None', self.image.levels)
        if levels is None:
            return None
        low, high = levels
        return float(low), float(high)

    @levels.setter
    def levels(self, levels: tuple[float, float] | None) -> None:
        if levels is not None:
            low, high = levels
            if not high > low:
                raise ValueError(
                    f'the white level must be above the black level: {levels}')
            levels = (low, high)
        self._levels = self._shownLevels = levels
        self.image.setLevels(levels)

    @property
    def autoLevels(self) -> tuple[float, float] | None:
        '''The percentiles that the display shows as black and as white.

        The display follows the frames: the levels are estimated from a
        subsample every few frames and smoothed over time, so that the
        picture does not flicker.  ``None`` turns it off.  Explicit
        :attr:`levels` win.

        Raises
        ------
        ValueError
            If the percentiles are not ``0 <= low < high <= 100``.
        '''
        return self._auto.percentiles if self._auto else None

    @autoLevels.setter
    def autoLevels(self, percentiles: tuple[float, float] | None) -> None:
        self._auto = (None if percentiles is None
                      else AutoLevels(percentiles, every=_AUTO_EVERY))

    def _followLevels(self, image: Image, info: FrameInfo | None) -> None:
        '''Show the frame between the levels that it comes with.

        Levels that were set explicitly win, then the percentiles of
        :attr:`autoLevels`.  The display is told only when the levels
        change, because explicit levels make pyqtgraph rescale every frame.
        '''
        wanted = self._levels
        if wanted is None and self._auto is not None:
            wanted = self._auto(image)
        if wanted is None and info:
            wanted = info.levels
        if wanted != self._shownLevels:
            self._shownLevels = wanted
            self.image.setLevels(wanted)

    def _setready(self) -> None:
        '''Allow the next frame, and show the one that waited.'''
        self._ready = True
        if self._pending is not None:
            self.setImage(*self._pending)

    @QtCore.Slot(np.ndarray)
    @QtCore.Slot(np.ndarray, object)
    def setImage(self, image: Image, info: FrameInfo | None = None) -> None:
        '''Display a new video frame and emit :attr:`newFrame`.

        If the throttle interval has not yet elapsed, the frame is
        buffered as the most recent pending frame; when the interval
        expires the buffered frame is displayed immediately so no extra
        latency accumulates.

        :attr:`newFrame` is emitted with the frame, or with the rendered
        composite scene when :attr:`composite` is ``True``, together with
        *info*.

        Parameters
        ----------
        image : Image
            The frame to display.
        info : FrameInfo, optional
            Capture metadata for *image*, passed on with :attr:`newFrame`.
        '''
        if self._ready:
            self._followLevels(image, info)
            self.image.setImage(image, autoLevels=False)
            self.newFrame.emit(
                self.screenshot() if self._composite else image, info)
            self._ready = False
            self._pending = None
            self._timer.start(self._interval)
        else:
            self._pending = (image, info)

    @property
    def fps(self) -> float | None:
        '''Effective display frame rate [frames per second].

        Returns :attr:`framerate` when display throttling is active,
        otherwise delegates to the source frame rate.
        This is the rate at which :attr:`newFrame` fires, and therefore
        the correct value to use when the screen is used as the source
        for a recorder.
        Returns ``None`` when no source is connected.
        '''
        if self._framerate is not None:
            return float(self._framerate)
        if self._source is not None:
            return self._source.fps
        return None

    @property
    def composite(self) -> bool:
        '''Emit the rendered scene via :attr:`newFrame`, not the raw frame.'''
        return self._composite

    @composite.setter
    def composite(self, value: bool) -> None:
        self._composite = bool(value)

    def screenshot(self) -> Image:
        '''Capture the widget (video + overlays) as an RGB numpy array.

        This is what the screen shows, with its filters, color map and
        overlays.  It is rendered when called, so it costs nothing until
        then (unlike :attr:`composite`, which renders every frame).

        Uses :meth:`QWidget.grab` to snapshot the widget's current visual
        state.  This avoids painter conflicts that arise from rendering the
        :class:`~pyqtgraph.GraphicsScene` directly while pyqtgraph may have
        its own internal painter active.

        Returns
        -------
        numpy.ndarray
            Array of shape ``(H, W, 3)`` and dtype ``uint8``, like every
            color frame (a grab is opaque, so it has no alpha channel).
            *H* and *W* are even: an odd last row or column is dropped,
            because video encoders need it.
            Returns an empty ``(0, 0, 3)`` array if the widget has no size.
        '''
        pixmap = self.grab()
        if pixmap.isNull():
            return np.empty((0, 0, 3), dtype=np.uint8)
        qimage = pixmap.toImage().convertToFormat(
            ImageFormat.Format_RGBA8888)
        w, h = qimage.width(), qimage.height()
        ptr = cast(Any, qimage.bits())
        if hasattr(ptr, 'setsize'):
            ptr.setsize(h * w * 4)
        scene = np.frombuffer(ptr, np.uint8).reshape(h, w, 4)
        # H.264 cannot encode an odd number of pixels
        return scene[:h // 2 * 2, :w // 2 * 2, :3].copy()

    def addOverlay(self, item: QtWidgets.QGraphicsItem) -> None:
        '''Add a graphics item to the view

        Register overlays for visibility control.

        Parameters
        ----------
        item : pyqtgraph.GraphicsObject
            The overlay item to add.
        '''
        self.view.addItem(item)
        self._overlays.append(item)

    def removeOverlay(self, item: QtWidgets.QGraphicsItem) -> None:
        '''Remove a previously added graphics item from the view.

        Parameters
        ----------
        item : pyqtgraph.GraphicsObject
            The overlay item to remove.
        '''
        self.view.removeItem(item)
        self._overlays.remove(item)

    @property
    def overlaysVisible(self) -> bool:
        '''Whether any registered overlay is currently visible.'''
        return any(item.isVisible() for item in self._overlays)

    @overlaysVisible.setter
    def overlaysVisible(self, visible: bool) -> None:
        for item in self._overlays:
            item.setVisible(visible)

    def sizeHint(self) -> QtCore.QSize:
        '''Return the source frame size as the preferred widget size.'''
        if self._videoShape is not None:
            return self._videoShape
        return super().sizeHint()

    def hasHeightForWidth(self) -> bool:
        '''Return True once a video frame shape is known.'''
        return self._videoShape is not None

    def heightForWidth(self, width: int) -> int:
        '''Return the height that preserves the source aspect ratio.'''
        if self._videoShape is None:
            return super().heightForWidth(width)
        return width * self._videoShape.height() // self._videoShape.width()

    @QtCore.Slot(QtCore.QSize)
    def updateShape(self, shape: QtCore.QSize) -> None:
        '''Resize the display to match the video frame dimensions.

        The first shape fits the window to the video at once; later ones
        wait until the shape has not changed for a moment (see
        :data:`_FIT_DELAY`), and the video is scaled in the window meanwhile.

        Ignores shapes that are not positive: zero, which :class:`QCamera`
        emits as a sentinel before ``width`` / ``height`` are registered
        as camera properties, and ``-1``, which a driver can report before
        the stream runs.

        Parameters
        ----------
        shape : QtCore.QSize
            New frame dimensions.
        '''
        if shape.width() <= 0 or shape.height() <= 0:
            return
        logger.debug(f'Resizing to {shape}')
        first = self._videoShape is None
        self._videoShape = shape
        self.updateGeometry()
        widget = self
        while (widget := widget.parentWidget()) is not None:
            widget.updateGeometry()
        if first:
            self._fitToVideo()
            return
        # A control that changes the shape (a slider that is dragged) does so
        # at every step.  Resizing the window each time moves the controls
        # from under the pointer, so the video is scaled in the window as it
        # is, and the window is fitted when the changes have stopped.
        self._showAll(shape.width(), shape.height())
        self._fitTimer.start()

    @QtCore.Slot()
    def _fitToVideo(self) -> None:
        '''Resize the containing window to fit the video at native resolution.

        Caps at the available area of whichever screen the window is on,
        less its title bar and borders, which count against the screen: a
        window whose frame is too large is shrunk by the window manager, and
        the video then has bars.  Width and height are adjusted to preserve
        the video aspect ratio.
        '''
        shape = self._videoShape
        if shape is None:
            return
        window = cast(QtWidgets.QWidget, self.window())
        screen = cast(QtGui.QScreen,
                      QtWidgets.QApplication.screenAt(window.pos())
                      or QtWidgets.QApplication.primaryScreen())
        available = screen.availableGeometry()
        frame = window.frameGeometry()
        sh = window.sizeHint()
        w_extra = sh.width() - shape.width() + frame.width() - window.width()
        h_extra = (sh.height() - shape.height()
                   + frame.height() - window.height())
        ideal_w = min(shape.width(), available.width() - w_extra)
        ideal_h = min(shape.height(), available.height() - h_extra)
        if ideal_w * shape.height() > ideal_h * shape.width():
            ideal_w = ideal_h * shape.width() // shape.height()
        else:
            ideal_h = ideal_w * shape.height() // shape.width()
        new_w = max(1, ideal_w) + sh.width() - shape.width()
        new_h = max(1, ideal_h) + sh.height() - shape.height()
        self.setMinimumSize(min(shape.width() // 2, ideal_w),
                            min(shape.height() // 2, ideal_h))
        if (new_w, new_h) != (window.width(), window.height()):
            window.resize(new_w, new_h)
        # A window that cannot take the new size does not resize, so the
        # range is not left to resizeEvent.
        self._showAll(shape.width(), shape.height())

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        '''Fit a window that nobody has sized to the video.

        The shape of the video is usually known before the screen is in
        its window (an application builds the screen, then puts it in a
        main window), so the window that the shape fitted was not the one
        that is shown.  A window that has been resized, by the application,
        by the user or by an earlier fit, is left alone.
        '''
        super().showEvent(event)
        if not cast(QtWidgets.QWidget, self.window()).testAttribute(
                QtCore.Qt.WidgetAttribute.WA_Resized):
            self._fitToVideo()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        '''Update the ViewBox range to match the video after a resize.'''
        super().resizeEvent(event)
        # The first resize arrives while the base class is built, before
        # there is a shape.
        shape = getattr(self, '_videoShape', None)
        if shape is not None:
            self._showAll(shape.width(), shape.height())

    def _showAll(self, width: int, height: int) -> None:
        '''Make the view show the region of *width* by *height* pixels.'''
        self.view.setRange(xRange=(0, width), yRange=(0, height),
                           padding=0, update=True)
