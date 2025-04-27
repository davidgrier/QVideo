from QVideo.lib import QVideoScreen
from pyqtgraph.Qt.QtCore import QEvent
from pyqtgraph.Qt.QtWidgets import (QWidget, QHBoxLayout)


class demo(QWidget):

    def __init__(self, CameraWidget, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.screen = QVideoScreen(self)
        self.cameraWidget = CameraWidget().start()
        self.screen.setSource(self.cameraWidget.source)
        self.setupUi()

    def setupUi(self) -> None:
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.cameraWidget)


def main():
    from pyqtgraph.Qt.QtWidgets import QApplication
    from QVideo.cameras.choose_camera import choose_camera_widget
    import sys

    CameraWidget = choose_camera_widget()

    app = QApplication(sys.argv)
    widget = demo(CameraWidget)
    widget.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
