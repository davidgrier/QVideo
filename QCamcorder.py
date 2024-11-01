from PyQt5.QtWidgets import QWidget
from PyQt5 import uic
from PyQt5.QtCore import (pyqtSlot, QEvent)


class QCamcorder(QWidget):

    UIFILE = 'QCamcorder.ui'

    def __init__(self, *args, cameraWidget=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraWidget = cameraWidget
        self.camera = self.cameraWidget.camera
        self.source = self.cameraWidget.source
        self.dvr.source = self.source
        self.setupUi()
        self.connectSignals()

    def setupUi(self) -> None:
        uic.loadUi(self.UIFILE, self)
        self.controls.layout().addWidget(self.cameraWidget)
        self.updateShape()

    def connectSignals(self) -> None:
        self.source.newFrame.connect(self.screen.setImage)
        self.camera.shapeChanged.connect(self.updateShape)
        self.dvr.playing.connect(self.dvrPlayback)

    def updateShape(self) -> None:
        self.screen.updateShape(self.camera.shape)

    @pyqtSlot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        if playback:
            self.source.newFrame.disconnect(self.screen.setImage)
            self.dvr.newFrame.connect(self.screen.setImage)
        else:
            self.source.newFrame.connect(self.screen.setImage)
        self.cameraWidget.setDisabled(playback)


def main() -> None:
    from PyQt5.QtWidgets import QApplication
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
