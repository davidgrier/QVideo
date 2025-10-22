from pyqtgraph.Qt.QtWidgets import QWidget
from pyqtgraph.Qt import uic
from pyqtgraph.Qt.QtCore import pyqtSlot
from pathlib import Path


class QCamcorder(QWidget):

    UIFILE = 'QCamcorder.ui'

    def __init__(self, cameraWidget, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cameraWidget = cameraWidget
        self.source = self.cameraWidget.source
        self._setupUi()
        self._connectSignals()

    def _setupUi(self) -> None:
        uifile = str(Path(__file__).parent / self.UIFILE)
        uic.loadUi(uifile, self)
        self.controls.layout().addWidget(self.cameraWidget)
        self.updateShape()

    def _connectSignals(self) -> None:
        self.source.newFrame.connect(self.screen.setImage)
        self.source.shapeChanged.connect(self.updateShape)
        self.dvr.source = self.source
        self.dvr.playing.connect(self.dvrPlayback)

    def updateShape(self) -> None:
        self.screen.updateShape(self.source.shape)

    @pyqtSlot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        if playback:
            self.source.newFrame.disconnect(self.screen.setImage)
            self.dvr.newFrame.connect(self.screen.setImage)
        else:
            self.source.newFrame.connect(self.screen.setImage)
        self.cameraWidget.setDisabled(playback)


def main() -> None:
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    app = pg.mkQApp()
    camera = choose_camera()
    widget = QCamcorder(camera.start())
    widget.show()
    pg.exec()


if __name__ == '__main__':
    main()
