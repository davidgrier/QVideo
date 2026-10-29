'''Live video display widget with mouse-aware graphical overlay support.'''
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib.QVideoSource import QVideoSource
from QVideo.lib.QFrameRelay import QFrameRelay
from QVideo.lib.videotypes import FrameInfo
from QVideo.lib.videotypes import Image
import numpy as np
import pyqtgraph as pg
from pyqtgraph import GraphicsLayoutWidget, ImageItem
import logging


logger = logging.getLogger(__name__)

__all__ = ['QVideoScreen']


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
        it carries the rendered ViewBox scene (video + overlays) as an
        ``(H, W, 4)`` RGBA uint8 array.
    colormap : str | None
        Colormap name for false-color display of grayscale frames.
        Accepts any matplotlib colormap name (e.g. ``'inferno'``,
        ``'viridis'``) or a pyqtgraph built-in name.
        Set to ``None`` (default) to display in grayscale.
        Has no effect on color (3-channel) frames.

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
        self._ready = True
        self._pending: Image | None = None
        self._overlays: list[object] = []
        self._composite = False
        self._videoShape: QtCore.QSize | None = None
        self._source: QVideoSource | None = None
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._setready)
        self._setupUi()

    def _setupUi(self) -> None:
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.view = self.addViewBox(enableMenu=False,
                                    enableMouse=False)
        self.view.invertY(True)
        self.view.setAspectLocked(True)
        self.view.setDefaultPadding(0)
        sz = self.size()
        self.view.setRange(xRange=(0, sz.width()),
                           yRange=(0, sz.height()),
                           padding=0, update=True)
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
        if source is None:
            return
        if source.shape is not None:
            self.updateShape(source.shape)
        self._source.shapeChanged.connect(self.updateShape)
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
        self._colormap = name
        if name is None:
            self.image.setLookupTable(None)
            return
        try:
            cm = pg.colormap.get(name, source='matplotlib')
        except (KeyError, FileNotFoundError, ImportError):
            cm = pg.colormap.get(name)
        self.image.setColorMap(cm)

    def _setready(self) -> None:
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
            self.image.setImage(image, autoLevels=False)
            self.newFrame.emit(
                self._renderComposite() if self._composite else image, info)
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

    def _renderComposite(self) -> Image:
        '''Capture the widget (video + overlays) as an RGB numpy array.

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
        try:
            fmt = QtGui.QImage.Format.Format_RGBA8888
        except AttributeError:
            fmt = QtGui.QImage.Format_RGBA8888
        qimage = pixmap.toImage().convertToFormat(fmt)
        w, h = qimage.width(), qimage.height()
        ptr = qimage.bits()
        if hasattr(ptr, 'setsize'):
            ptr.setsize(h * w * 4)
        scene = np.frombuffer(ptr, np.uint8).reshape(h, w, 4)
        # H.264 cannot encode an odd number of pixels
        return scene[:h // 2 * 2, :w // 2 * 2, :3].copy()

    def addOverlay(self, item: object) -> None:
        '''Add a graphics item to the view

        Register overlays for visibility control.

        Parameters
        ----------
        item : pyqtgraph.GraphicsObject
            The overlay item to add.
        '''
        self.view.addItem(item)
        self._overlays.append(item)

    def removeOverlay(self, item: object) -> None:
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
        self._videoShape = shape
        self.updateGeometry()
        widget = self
        while (widget := widget.parentWidget()) is not None:
            widget.updateGeometry()
        self._fitToVideo()

    @QtCore.Slot()
    def _fitToVideo(self) -> None:
        '''Resize the containing window to fit the video at native resolution.

        Caps at the full available area of whichever screen the window is on,
        so the result is the same whether the window has been shown or not.
        Width and height are adjusted to preserve the video aspect ratio.
        '''
        if not self.hasHeightForWidth():
            return
        shape = self._videoShape
        window = self.window()
        screen = (QtWidgets.QApplication.screenAt(window.pos())
                  or QtWidgets.QApplication.primaryScreen())
        available = screen.availableGeometry()
        sh = window.sizeHint()
        w_extra = sh.width() - shape.width()
        h_extra = sh.height() - shape.height()
        ideal_w = min(shape.width(), available.width() - w_extra)
        ideal_h = min(shape.height(), available.height() - h_extra)
        if ideal_w * shape.height() > ideal_h * shape.width():
            ideal_w = ideal_h * shape.width() // shape.height()
        else:
            ideal_h = ideal_w * shape.height() // shape.width()
        new_w = max(1, ideal_w) + w_extra
        new_h = max(1, ideal_h) + h_extra
        self.setMinimumSize(min(shape.width() // 2, ideal_w),
                            min(shape.height() // 2, ideal_h))
        if (new_w, new_h) != (window.width(), window.height()):
            window.resize(new_w, new_h)
        # A window that cannot take the new size does not resize, so the
        # range is not left to resizeEvent.
        self.view.setRange(xRange=(0, shape.width()),
                           yRange=(0, shape.height()),
                           padding=0, update=True)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        '''Fit a window that nobody has sized to the video.

        The shape of the video is usually known before the screen is in
        its window (an application builds the screen, then puts it in a
        main window), so the window that the shape fitted was not the one
        that is shown.  A window that has been resized, by the application,
        by the user or by an earlier fit, is left alone.
        '''
        super().showEvent(event)
        if not self.window().testAttribute(QtCore.Qt.WA_Resized):
            self._fitToVideo()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        '''Update the ViewBox range to match the video after a resize.'''
        super().resizeEvent(event)
        shape = getattr(self, '_videoShape', None)
        if shape is not None:
            self.view.setRange(
                xRange=(0, shape.width()),
                yRange=(0, shape.height()),
                padding=0, update=True)
