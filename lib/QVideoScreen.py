from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QSize)
from PyQt5.QtGui import (QMouseEvent, QWheelEvent)
import pyqtgraph as pg
import numpy as np
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QVideoScreen(pg.GraphicsLayoutWidget):
    '''Video screen widget that emits signals for mouse events
    '''

    mousePress = pyqtSignal(QMouseEvent)
    mouseRelease = pyqtSignal(QMouseEvent)
    mouseMove = pyqtSignal(QMouseEvent)
    mouseWheel = pyqtSignal(QWheelEvent)

    def __init__(self, *args, **kwargs) -> None:
        pg.setConfigOptions(imageAxisOrder='row-major')
        super().__init__(*args, **kwargs)
        self.setupUi()
        self.pauseSignals(False)

    def setupUi(self) -> None:
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.image = pg.ImageItem()
        self.view = self.addViewBox(invertY=True, lockAspect=True)
        self.view.addItem(self.image)
        self.updateShape(QSize(640, 480))

    def sizeHint(self) -> QSize:
        return self._size

    def minimumSizeHint(self) -> QSize:
        return self._size / 2

    @pyqtSlot(np.ndarray)
    def setImage(self, image: np.ndarray) -> None:
        self.image.setImage(image, autoLevels=False)

    @pyqtSlot(QSize)
    def updateShape(self, shape: QSize) -> None:
        logger.debug(f'Resizing to {shape}')
        self.view.setRange(xRange=(0, shape.width()),
                           yRange=(0, shape.height()),
                           padding=0, update=True)
        self._size = shape
        self.update()

    @pyqtSlot(bool)
    def pauseSignals(self, value: bool) -> None:
        self._pause = value

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.mousePress.emit(event)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.mouseRelease.emit(event)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._pause:
            self.mouseMove.emit(event)
        super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._pause:
            self.mouseWheel.emit(event)
        super().wheelEvent(event)
