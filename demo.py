from PyQt5.QtWidgets import (QWidget, QHBoxLayout)
from QVideoScreen import QVideoScreen
# from QNoiseWidget import QNoiseWidget as QCameraWidget
from QOpenCVWidget import QOpenCVWidget as QCameraWidget
# from QSpinnakerWidget import QSpinnakerWidget as QCameraWidget


class demo(QWidget):

    def __init__(self):
        super().__init__()
        self.source = QCameraWidget(self)
        self.screen = QVideoScreen(self, camera=self.source.camera)
        self.setupUi()

    def setupUi(self):
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.source)
        self.update()


def main():
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = demo()
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
