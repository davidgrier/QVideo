from PyQt5.QtWidgets import QWidget
from PyQt5 import uic
from PyQt5.QtCore import (pyqtSlot, QEvent)


class QCamcorder(QWidget):

    UIFILE = 'QCamcorder.ui'

    def __init__(self, *args, cameraWidget=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraWidget = cameraWidget
        self.camera = self.cameraWidget.camera
        self.setupUi()
        self.connectSignals()

    def setupUi(self) -> None:
        uic.loadUi(self.UIFILE, self)
        self.controls.layout().addWidget(self.cameraWidget)
        self.updateShape()

    def connectSignals(self) -> None:
        self.camera.newFrame.connect(self.screen.setImage)
        self.camera.shapeChanged.connect(self.updateShape)
        self.dvr.playing.connect(self.dvrPlayback)
        self.dvr.source = self.camera

    def closeEvent(self, event: QEvent) -> None:
        self.cameraWidget.close()

    def updateShape(self) -> None:
        self.screen.updateShape(self.camera.shape)

    @pyqtSlot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        if playback:
            self.camera.newFrame.disconnect(self.screen.setImage)
            self.dvr.newFrame.connect(self.screen.setImage)
        else:
            self.camera.newFrame.connect(self.screen.setImage)
        self.cameraWidget.setDisabled(playback)


def main() -> None:
    from PyQt5.QtWidgets import QApplication
    from QVideo.cameras.choose_camera import choose_camera_widget
    import sys

    CameraWidget = choose_camera_widget()

    app = QApplication([])
    widget = QCamcorder(cameraWidget=CameraWidget())
    widget.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
