from PyQt5.QtCore import (pyqtSlot, QSize)
import pyqtgraph as pg
from QVideo.filters.FilterBank import FilterBank
import numpy as np
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoScreen(pg.GraphicsLayoutWidget):
    '''Video screen widget'''

    def __init__(self, *args, **kwargs) -> None:
        pg.setConfigOptions(imageAxisOrder='row-major')
        super().__init__(*args, **kwargs)
        self.filter = FilterBank()
        self.setupUi()

    def setupUi(self) -> None:
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.view = self.addViewBox(invertY=True,
                                    lockAspect=True,
                                    enableMenu=False,
                                    enableMouse=False)
        self.image = pg.ImageItem()
        self.view.addItem(self.image)
        self.updateShape(QSize(640, 480))

    def sizeHint(self) -> QSize:
        return self._size

    def minimumSizeHint(self) -> QSize:
        return self._size / 2

    @pyqtSlot(np.ndarray)
    def setImage(self, image: np.ndarray) -> None:
        self.image.setImage(self.filter(image), autoLevels=False)

    @pyqtSlot(QSize)
    def updateShape(self, shape: QSize) -> None:
        logger.debug(f'Resizing to {shape}')
        self.view.setRange(xRange=(0, shape.width()),
                           yRange=(0, shape.height()),
                           padding=0, update=True)
        self._size = shape
        self.update()
