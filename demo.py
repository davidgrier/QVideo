from PyQt5.QtWidgets import (QWidget, QHBoxLayout)
from PyQt5.QtCore import QEvent
from QVideo.lib import QVideoScreen


class demo(QWidget):

    def __init__(self, QCameraWidget, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.screen = QVideoScreen(self)
        self.cameraWidget = QCameraWidget(self)
        self.camera = self.cameraWidget.camera
        self.setupUi()
        self.connectSignals()

    def setupUi(self) -> None:
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.cameraWidget)
        self.updateShape()

    def connectSignals(self) -> None:
        self.camera.newFrame.connect(self.screen.setImage)
        self.camera.shapeChanged.connect(self.updateShape)

    def closeEvent(self, event: QEvent) -> None:
        self.cameraWidget.close()

    def updateShape(self) -> None:
        self.screen.updateShape(self.camera.shape)
        self.update()


def main():
    from PyQt5.QtWidgets import QApplication
    from QVideo.cameras.choose_camera import choose_camera_widget
    import sys

    CameraWidget = choose_camera_widget()

    app = QApplication([])
    widget = demo(CameraWidget)
    widget.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
