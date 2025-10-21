from QVideo.lib import (QVideoScreen, QCameraTree)
from pyqtgraph.Qt.QtCore import QEvent
from pyqtgraph.Qt.QtWidgets import (QWidget, QHBoxLayout)


class demo(QWidget):

    def __init__(self, cameraWidget: QCameraTree, **kwargs) -> None:
        super().__init__(**kwargs)
        self.screen = QVideoScreen(self)
        self.cameraWidget = cameraWidget
        self.screen.setSource(self.cameraWidget.source)
        self.setupUi()

    def setupUi(self) -> None:
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.cameraWidget)


def main():
    from pyqtgraph.Qt.QtWidgets import QApplication
    from QVideo.cameras.choose_camera import choose_qcamera
    import sys

    app = QApplication(sys.argv)
    widget = demo(choose_qcamera())
    widget.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
