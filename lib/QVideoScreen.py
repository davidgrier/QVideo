'''Live video display widget with mouse-aware graphical overlay support.'''
from QVideo.lib.QVideoSource import QVideoSource
from QVideo.lib.QFilterBank import QFilterBank
from QVideo.lib.types import Image
from pyqtgraph.Qt import QtCore
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
        The video source. Setting this connects :attr:`newFrame` and
        :attr:`shapeChanged` to the display.
    '''

    def __init__(self, *args,
                 size: tuple[int, int] = (640, 480),
                 framerate: int | None = None,
                 **kwargs) -> None:
        super().__init__(*args, size=size, **kwargs)
        self.framerate = framerate
        self._ready = True
        self._pending = None
        self._setupUi()
        self._timer = QtCore.QTimer()
        self._source = None
        self.filter = QFilterBank(self)
        self.filter.setVisible(False)
        self._overlays = []

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
        '''Add a graphics item to the view and register it for visibility control.

        Parameters
        ----------
        item : pyqtgraph.GraphicsObject
            The overlay item to add.
        '''
        self.view.addItem(item)
        self._overlays.append(item)

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

    @QtCore.pyqtSlot(np.ndarray)
    def setImage(self, image: Image) -> None:
        '''Display a new video frame, subject to frame-rate throttling.

        Passes the frame through :attr:`filter` before display.  If the
        throttle interval has not yet elapsed, the frame is buffered as the
        most recent pending frame; when the interval expires the buffered
        frame is displayed immediately so no extra latency accumulates.

        Parameters
        ----------
        image : Image
            The frame to display.
        '''
        if self._ready:
            self.image.setImage(self.filter(image), autoLevels=False)
            self._ready = False
            self._pending = None
            self._timer.singleShot(self._interval, self._setready)
        else:
            self._pending = image

    def sizeHint(self) -> QtCore.QSize:
        '''Return the source frame size as the preferred widget size.'''
        if self.source is not None:
            return self.source.shape
        return super().sizeHint()

    def hasHeightForWidth(self) -> bool:
        '''Return True when the source frame size is known.'''
        return self.source is not None

    def heightForWidth(self, width: int) -> int:
        '''Return the height that preserves the source aspect ratio.'''
        if self.source is not None:
            shape = self.source.shape
            return width * shape.height() // shape.width()
        return super().heightForWidth(width)

    @QtCore.pyqtSlot(QtCore.QSize)
    def updateShape(self, shape: QtCore.QSize) -> None:
        '''Resize the display to match the video frame dimensions.

        Parameters
        ----------
        shape : QtCore.QSize
            New frame dimensions.
        '''
        logger.debug(f'Resizing to {shape}')
        self.view.setRange(xRange=(0, shape.width()),
                           yRange=(0, shape.height()),
                           padding=0, update=True)
        self.setMinimumSize(shape / 2)
        self.updateGeometry()
        QtCore.QTimer.singleShot(0, self._fitToVideo)

    def resizeEvent(self, event) -> None:
        '''Queue an aspect-ratio correction after the layout reflows.'''
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._fitToVideo)

    @QtCore.pyqtSlot()
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
