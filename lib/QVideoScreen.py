from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QSize)
from PyQt5.QtGui import (QMouseEvent, QWheelEvent)
import pyqtgraph as pg
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoScreen(pg.GraphicsLayoutWidget):

    mousePress = pyqtSignal(QMouseEvent)
    mouseRelease = pyqtSignal(QMouseEvent)
    mouseMove = pyqtSignal(QMouseEvent)
    mouseWheel = pyqtSignal(QWheelEvent)

    options = dict(enableMenu=False,
                   enableMouse=False,
                   invertY=True,
                   lockAspect=True)

    def __init__(self, *args, **kwargs):
        pg.setConfigOptions(imageAxisOrder='row-major')
        super().__init__(*args, **kwargs)
        self.setupUi()
        self.pauseSignals(False)

    def setupUi(self):
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.image = pg.ImageItem()
        self.view = self.addViewBox(**self.options)
        self.view.addItem(self.image)
        self.updateShape(QSize(640, 480))
        self.setImage = self.image.setImage

    def sizeHint(self):
        return self._size

    def minimumSizeHint(self):
        return self._size / 2

    @pyqtSlot(QSize)
    def updateShape(self, shape):
        logger.debug(f'Resizing to {shape}')
        self.view.setRange(xRange=(0, shape.width()),
                           yRange=(0, shape.height()),
                           padding=0, update=True)
        self._size = shape
        self.update()

    @pyqtSlot(bool)
    def pauseSignals(self, value):
        self._pause = value

    def mousePressEvent(self, event):
        self.mousePress.emit(event)
        event.accept()

    def mouseReleaseEvent(self, event):
        self.mouseRelease.emit(event)
        event.accept()

    def mouseMoveEvent(self, event):
        if not self._pause:
            self.mouseMove.emit(event)
        event.accept()

    def wheelEvent(self, event):
        if not self._pause:
            self.mouseWheel.emit(event)
        event.accept()
