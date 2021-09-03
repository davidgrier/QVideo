from PyQt5.QtCore import (QThread, pyqtSignal, pyqtSlot, pyqtProperty)
from PyQt5.QtGui import (QMouseEvent, QWheelEvent)
import pyqtgraph as pg
import numpy as np
from QVideoCamera import QVideoCamera
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QVideoScreen(pg.GraphicsLayoutWidget):

    mousePress   = pyqtSignal(QMouseEvent)
    mouseRelease = pyqtSignal(QMouseEvent)
    mouseMove    = pyqtSignal(QMouseEvent)
    mouseWheel   = pyqtSignal(QWheelEvent)

    def __init__(self, *args, camera=None, **kwargs):
        pg.setConfigOptions(imageAxisOrder='row-major')
        super().__init__(*args, **kwargs)
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.image = pg.ImageItem()
        self.view = self.addViewBox(enableMenu=False,
                                    enableMouse=False,
                                    invertY=True,
                                    lockAspect=True)
        self.view.addItem(self.image)
        self._filters = []
        self.pauseSignals(False)
        self.camera = camera

    @pyqtProperty(QVideoCamera)
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, camera):
        logger.debug(f'Setting camera: {type(camera)}')
        self._camera = camera
        if camera is None:
            return
        self.updateShape()
        self.thread = QThread()
        camera.moveToThread(self.thread)
        self.thread.started.connect(camera.run)
        camera.finished.connect(self.thread.quit)
        camera.finished.connect(self.camera.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.source = camera
        self.thread.start(QThread.TimeCriticalPriority)

    def updateShape(self):
        self.resize(self.camera.width, self.camera.height)
        self.view.setRange(xRange=(0, self.camera.width),
                           yRange=(0, self.camera.height),
                           padding=0, update=True)

    @pyqtProperty(object)
    def source(self):
        return self._source

    @source.setter
    def source(self, source):
        try:
            self._source.newFrame.disconnect(self.updateImage)
        except AttributeError:
            pass
        self._source = source or self.thread
        self._source.newFrame.connect(self.updateImage)

    @pyqtSlot(np.ndarray)
    def updateImage(self, image):
        self.image.setImage(image)

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
