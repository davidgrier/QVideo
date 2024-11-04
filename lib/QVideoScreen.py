from QVideo.lib import QVideoSource
from PyQt5.QtCore import (QThread, pyqtSlot, QSize)
from pyqtgraph import (GraphicsLayoutWidget, ImageItem)
import numpy as np
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoScreen(GraphicsLayoutWidget):
    '''Video screen widget'''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setupUi()
        self._source = None

    def setupUi(self) -> None:
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.view = self.addViewBox(invertY=True,
                                    lockAspect=True,
                                    enableMenu=False,
                                    enableMouse=False)
        self.view.setDefaultPadding(0)
        self.image = ImageItem(axisOrder='row-major')
        self.view.addItem(self.image)

    def sizeHint(self) -> QSize:
        return self._size

    def minimumSizeHint(self) -> QSize:
        return self._size / 2

    def source(self) -> QVideoSource:
        return self._source

    def setSource(self, source: QVideoSource) -> None:
        '''Connect video source to view screen

        Arguments
        ---------
        camera : QVideoSource
            Video source that will provide frames to display
        '''
        assert(isinstance(source, QVideoSource))
        if self._source is not None:
            self._source = None
        self._source = source
        self.updateShape(self._source.source.shape)
        self._source.source.shapeChanged.connect(self.updateShape)
        self._source.newFrame.connect(self.setImage)

    @pyqtSlot()
    def start(self):
        self._source.start()

    @pyqtSlot(np.ndarray)
    def setImage(self, image: np.ndarray) -> None:
        self.image.setImage(image, autoLevels=False)

    @pyqtSlot(QSize)
    def updateShape(self, shape: QSize) -> None:
        logger.debug(f'Resizing to {shape}')
        self.view.setRange(xRange=(0, shape.width()),
                           yRange=(0, shape.height()),
                           padding=0, update=True)
        self.resize(shape.width(), shape.height())
        self._size = shape


def main() -> None:
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication([])
    widget = QVideoScreen()
    widget.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
