from QVideo.lib import (QCamera, QVideoSource)
from pyqtgraph.Qt.QtCore import (pyqtProperty, pyqtSlot, QSize)
from pyqtgraph import (GraphicsLayoutWidget, ImageItem)
import numpy as np
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoScreen(GraphicsLayoutWidget):

    '''A video display widget for showing frames from a QVideoSource.

    Inherits
    --------
    pyqtgraph.GraphicsLayoutWidget
        A graphics layout widget for displaying graphics items.

    Parameters
    ----------
    args : list
        Additional positional arguments to pass to the
        GraphicsLayoutWidget constructor.
    kwargs : dict
        Additional keyword arguments to pass to the
        GraphicsLayoutWidget constructor.

    Returns
    -------
    QVideoScreen : GraphicsLayoutWidget
        The video display widget.

    Properties
    ----------
    source : QVideoSource
        The video source object.

    Methods
    -------
    start() -> None
        Start the video source.
    setImage(image: np.ndarray) -> None
        Update the displayed image with a new frame.
    updateShape(shape: QSize) -> None
        Update the display shape based on the video source shape.
    '''

    def __init__(self, *args,
                 size: tuple[int, int] = (640, 480),
                 **kwargs) -> None:
        super().__init__(*args, size=size, **kwargs)
        self._setupUi()
        self._source = None

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

    @pyqtProperty(QVideoSource)
    def source(self) -> QVideoSource:
        return self._source

    @source.setter
    def source(self, source: QVideoSource) -> None:
        self._source = source
        self.updateShape(source.source.shape)
        self._source.shapeChanged.connect(self.updateShape)
        self._source.newFrame.connect(self.setImage)

    @pyqtSlot()
    def start(self):
        self._source.start()

    @pyqtSlot(np.ndarray)
    def setImage(self, image: QCamera.Image) -> None:
        self.image.setImage(image, autoLevels=False)

    @pyqtSlot(QSize)
    def updateShape(self, shape: QSize) -> None:
        logger.debug(f'Resizing to {shape}')
        self.view.setRange(xRange=(0, shape.width()),
                           yRange=(0, shape.height()),
                           padding=0, update=True)
        self.setMinimumSize(shape / 2)


def main() -> None:
    import pyqtgraph as pg

    app = pg.mkQApp()
    widget = QVideoScreen()
    widget.show()
    pg.exec()


if __name__ == '__main__':
    main()
