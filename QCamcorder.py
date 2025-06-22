from pyqtgraph.Qt.QtWidgets import QWidget
from pyqtgraph.Qt import uic
from pyqtgraph.Qt.QtCore import pyqtSlot


class QCamcorder(QWidget):

    UIFILE = 'QCamcorder.ui'

    def __init__(self, *args, cameraWidget=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraWidget = cameraWidget
        self.source = self.cameraWidget.source
        self.setupUi()
        self.dvr.source = self.source
        self.connectSignals()

    def setupUi(self) -> None:
        uic.loadUi(self.UIFILE, self)
        self.controls.layout().addWidget(self.cameraWidget)
        self.updateShape()

    def connectSignals(self) -> None:
        self.source.newFrame.connect(self.screen.setImage)
        self.source.shapeChanged.connect(self.updateShape)
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
    from pyqtgraph.Qt.QtWidgets import QApplication
    from QVideo.cameras.choose_camera import choose_camera_widget
    import sys

    CameraWidget = choose_camera_widget()

    app = QApplication([])
    cameraWidget = CameraWidget().start()
    widget = QCamcorder(cameraWidget=cameraWidget)
    widget.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
