'''Live video display widget with mouse-aware graphical overlay support.'''
from qtpy import QtCore, QtGui
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

    #: Emitted after each displayed frame.
    newFrame = QtCore.Signal(np.ndarray)

    def __init__(self, *args,
                 size: tuple[int, int] = (640, 480),
                 framerate: int | None = None,
                 **kwargs) -> None:
        super().__init__(*args, size=size, **kwargs)
        self.framerate = framerate
        self._ready = True
        self._pending = None
        self._overlays = []
        self._composite = False
        self._videoShape = None
        self._setupUi()
        self._timer = QtCore.QTimer()
        self._source = None
        self.filter = QFilterBank(self)
        self.filter.setVisible(False)

    def _setupUi(self) -> None:
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.view = self.addViewBox(enableMenu=False,
                                    enableMouse=False)
        self.view.invertY(True)
        self.view.setAspectLocked(True)
        self.view.setDefaultPadding(0)
        self.updateShape(self.size())
        self.image = ImageItem(axisOrder='row-major')
        self.view.addItem(self.image)

    def addOverlay(self, item) -> None:
        '''Add a graphics item to the view

        Register overlays for visibility control.

        Parameters
        ----------
        item : pyqtgraph.GraphicsObject
            The overlay item to add.
        '''
        self.view.addItem(item)
        self._overlays.append(item)

    def removeOverlay(self, item) -> None:
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

    @property
    def source(self) -> QVideoSource:
        '''The video source providing frames to display.'''
        return self._source

    @source.setter
    def source(self, source: QVideoSource) -> None:
        if self._source is not None:
            self._source.shapeChanged.disconnect(self.updateShape)
            self._source.newFrame.disconnect(self.setImage)
        self._source = source
        self.updateShape(source.shape)
        self._source.shapeChanged.connect(self.updateShape)
        self._source.newFrame.connect(self.setImage)

    @property
    def fps(self) -> float | None:
        '''Effective display frame rate [frames per second].

        Returns :attr:`framerate` when display throttling is active, otherwise
        delegates to the source frame rate.  This is the rate at which
        :attr:`newFrame` fires, and therefore the correct value to use when
        the screen is connected to a recorder.  Returns ``None`` when no
        source is connected.
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
        ptr.setsize(h * w * 4)
        return np.frombuffer(ptr, np.uint8).reshape(h, w, 4).copy()

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
            self._timer.singleShot(self._interval, self._setready)
        else:
            self._pending = image

    def sizeHint(self) -> QtCore.QSize:
        '''Return the source frame size as the preferred widget size.'''
        if self._videoShape is not None:
            return self._videoShape
        if self.source is not None:
            return self.source.shape
        return super().sizeHint()

    def hasHeightForWidth(self) -> bool:
        '''Return True when a source is connected.'''
        return self.source is not None

    def heightForWidth(self, width: int) -> int:
        '''Return the height that preserves the source aspect ratio.'''
        shape = self._videoShape
        if shape is None and self.source is not None:
            shape = self.source.shape
        if shape is not None and shape.width() > 0:
            return width * shape.height() // shape.width()
        return super().heightForWidth(width)

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
        self.view.setRange(xRange=(0, shape.width()),
                           yRange=(0, shape.height()),
                           padding=0, update=True)
        self.setMinimumSize(shape / 2)
        self.updateGeometry()
        QtCore.QTimer.singleShot(0, self._fitToVideo)

    @QtCore.Slot()
    def _fitToVideo(self) -> None:
        '''Resize the containing window to match the video aspect ratio.

        Computes the height the widget should have given its current
        width and the source aspect ratio, then adjusts the top-level
        window height by the difference. Only has effect when a source
        is connected.
        '''
        if not self.hasHeightForWidth():
            return
        target_h = self.heightForWidth(self.width())
        if target_h <= 0:
            return
        window = self.window()
        needed = window.height() + target_h - self.height()
        if needed != window.height():
            window.resize(window.width(), needed)

    @classmethod
    def example(cls: 'QVideoScreen') -> None:  # pragma: no cover
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
