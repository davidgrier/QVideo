from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout)
from QVideoScreen import QVideoScreen
# from QNoiseSource import QNoiseSource as Camera
# from QOpenCVWidget import QOpenCVWidget as QCameraWidget
from QSpinnakerWidget import QSpinnakerWidget as QCameraWidget


class demo(QMainWindow):

    def __init__(self):
        super().__init__()
        self.source = QCameraWidget()
        self.screen = QVideoScreen(camera=self.source.camera)
        self.setupUi()

    def setupUi(self):
        self.widget = QWidget(self)
        self.layout = QHBoxLayout(self.widget)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.source)
        self.widget.setLayout(self.layout)
        self.setCentralWidget(self.widget)


def main():
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = demo()
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
