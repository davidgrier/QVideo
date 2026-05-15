'''Live video display widget with mouse-aware graphical overlay support.'''
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib.QVideoSource import QVideoSource
from QVideo.lib.QFilterBank import QFilterBank
from QVideo.lib.videotypes import Image
import numpy as np
from pyqtgraph import GraphicsLayoutWidget, ImageItem
import logging


logger = logging.getLogger(__name__)

__all__ = ['QVideoScreen']


class QVideoScreen(GraphicsLayoutWidget):

    '''Video display widget.

    Displays frames from a :class:`~QVideo.lib.QVideoSource` in real time,
    with optional frame-rate throttling and image filtering via
    :class:`~QVideo.lib.QFilterBank`.

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
        :attr:`newFrame` carries the filtered video frame.  When ``True``,
        it carries the rendered ViewBox scene (video + overlays) as an
        ``(H, W, 4)`` RGBA uint8 array.

    Signals
    -------
    newFrame(numpy.ndarray)
        Emitted after each displayed frame.  Carries either the filtered
        video frame or the rendered composite scene, depending on
        :attr:`composite`.
    '''

    newFrame = QtCore.Signal(np.ndarray)

    def __init__(self, *args,
                 size: tuple[int, int] = (640, 480),
                 framerate: int | None = None,
                 **kwargs) -> None:
        super().__init__(*args, size=size, **kwargs)
        self.framerate = framerate
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
        self.filter = QFilterBank(self)
        self.filter.setVisible(False)

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
            self._source.newFrame.disconnect(self.setImage)
        self._source = source
        if source is None:
            return
        if source.shape is not None:
            self.updateShape(source.shape)
        self._source.shapeChanged.connect(self.updateShape)
        self._source.newFrame.connect(self.setImage)

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

    def _setready(self) -> None:
        self._ready = True
        if self._pending is not None:
            self.setImage(self._pending)

    @QtCore.Slot(np.ndarray)
    def setImage(self, image: Image) -> None:
        '''Display a new video frame and emit :attr:`newFrame`.

        Passes the frame through :attr:`filter` before display.  If the
        throttle interval has not yet elapsed, the frame is buffered as the
        most recent pending frame; when the interval expires the buffered
        frame is displayed immediately so no extra latency accumulates.

        :attr:`newFrame` is emitted with the filtered frame, or with the
        rendered composite scene when :attr:`composite` is ``True``.

        Parameters
        ----------
        image : Image
            The frame to display.
        '''
        if self._ready:
            filtered = self.filter(image)
            self.image.setImage(filtered, autoLevels=False)
            self.newFrame.emit(
                self._renderComposite() if self._composite else filtered)
            self._ready = False
            self._pending = None
            self._timer.start(self._interval)
        else:
            self._pending = image

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
        '''Emit the rendered scene via :attr:`newFrame` instead of the raw frame.'''
        return self._composite

    @composite.setter
    def composite(self, value: bool) -> None:
        self._composite = bool(value)

    def _renderComposite(self) -> Image:
        '''Capture the widget (video + overlays) as an RGBA numpy array.

        Uses :meth:`QWidget.grab` to snapshot the widget's current visual
        state.  This avoids painter conflicts that arise from rendering the
        :class:`~pyqtgraph.GraphicsScene` directly while pyqtgraph may have
        its own internal painter active.

        Returns
        -------
        numpy.ndarray
            Array of shape ``(H, W, 4)`` and dtype ``uint8``.
            Returns an empty ``(0, 0, 4)`` array if the widget has no size.
        '''
        pixmap = self.grab()
        if pixmap.isNull():
            return np.empty((0, 0, 4), dtype=np.uint8)
        try:
            fmt = QtGui.QImage.Format.Format_RGBA8888
        except AttributeError:
            fmt = QtGui.QImage.Format_RGBA8888
        qimage = pixmap.toImage().convertToFormat(fmt)
        w, h = qimage.width(), qimage.height()
        ptr = qimage.bits()
        if hasattr(ptr, 'setsize'):
            ptr.setsize(h * w * 4)
        return np.frombuffer(ptr, np.uint8).reshape(h, w, 4).copy()

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
        w = self._videoShape.width()
        if w == 0:
            return super().heightForWidth(width)
        return width * self._videoShape.height() // w

    @QtCore.Slot(QtCore.QSize)
    def updateShape(self, shape: QtCore.QSize) -> None:
        '''Resize the display to match the video frame dimensions.

        Parameters
        ----------
        shape : QtCore.QSize
            New frame dimensions.
        '''
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
        Both width and height are adjusted while preserving the video aspect ratio.
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
            # resizeEvent will call view.setRange after the viewport shrinks
        else:
            self.view.setRange(xRange=(0, shape.width()),
                               yRange=(0, shape.height()),
                               padding=0, update=True)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        '''Update the ViewBox range to match the video after the viewport is resized.'''
        super().resizeEvent(event)
        shape = getattr(self, '_videoShape', None)
        if shape is not None:
            self.view.setRange(
                xRange=(0, shape.width()),
                yRange=(0, shape.height()),
                padding=0, update=True)

    @classmethod
    def example(cls: type['QVideoScreen']) -> None:  # pragma: no cover
        '''Demonstrate the video screen with a noise source.'''
        import pyqtgraph as pg
        from QVideo.cameras.Noise import QNoiseSource

        app = pg.mkQApp()
        screen = cls()
        source = QNoiseSource(blacklevel=48, whitelevel=128)
        screen.source = source.start()
        screen.show()
        pg.exec()


if __name__ == '__main__':  # pragma: no cover
    QVideoScreen.example()
