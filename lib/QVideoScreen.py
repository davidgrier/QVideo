from QVideo.lib import (QCamera, QVideoSource)
from pyqtgraph.Qt.QtCore import (pyqtProperty, pyqtSlot, QSize, QTimer)
from pyqtgraph import (GraphicsLayoutWidget, ImageItem, FileDialog)
from pyqtgraph.exporters import ImageExporter
import numpy as np
from pathlib import Path
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QVideoScreen(GraphicsLayoutWidget):

    '''Video display widget.

    Inherits
    --------
    pyqtgraph.GraphicsLayoutWidget

    Parameters
    ----------
    args : list
        Additional positional arguments to pass to the
        GraphicsLayoutWidget constructor.
    size : tuple(int, int)
        Starting dimensions of the VideoScreen.
        Default: (640, 480)
    framerate : int | None
        Maximum frames per second
        Default: None -- no delay
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
        video source object.

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
                 framerate: int | None = None,
                 **kwargs) -> None:
        super().__init__(*args, size=size, **kwargs)
        self.framerate = framerate
        self._ready = True
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
        self.timer = QTimer()

    @pyqtProperty(int)
    def framerate(self) -> int | None:
        return self._framerate

    @framerate.setter
    def framerate(self, framerate: int | None) -> None:
        self._framerate = framerate
        self._interval = 0 if framerate is None else int(1000/framerate)

    def _setready(self) -> None:
        self._ready = True

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
        if self._ready:
            self.image.setImage(image, autoLevels=False)
            self._ready = False
            self.timer.singleShot(self._interval, self._setready)

    @pyqtSlot()
    def saveImage(self) -> None:
        getname = FileDialog.getSaveFileName
        default = Path.home() / 'pyfab.png'
        filename, _ = getname(self, 'Save Image', str(default),
                              'PNG Files (*.png)')
        if filename is not None:
            exporter = ImageExporter(self.image)
            exporter.export(filename)
            logger.info('Saved screenshot.png')

    @pyqtSlot(QSize)
    def updateShape(self, shape: QSize) -> None:
        logger.debug(f'Resizing to {shape}')
        self.view.setRange(xRange=(0, shape.width()),
                           yRange=(0, shape.height()),
                           padding=0, update=True)
        self.setMinimumSize(shape / 2)

    @classmethod
    def example(cls: 'QVideoScreen') -> None:
        import pyqtgraph as pg
        from QVideo.cameras.Noise import QNoiseSource

        app = pg.mkQApp()
        screen = cls()
        source = QNoiseSource(blacklevel=48, whitelevel=128)
        screen.source = source.start()
        screen.show()
        pg.exec()


if __name__ == '__main__':
    QVideoScreen.example()
