from PyQt5.QtWidgets import (QWidget, QHBoxLayout)
from QVideo.lib import QVideoScreen


class demo(QWidget):

    def __init__(self, QCameraWidget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.screen = QVideoScreen(self)
        self.cameraWidget = QCameraWidget(self)
        self.camera = self.cameraWidget.camera
        self.setupUi()
        self.connectSignals()

    def setupUi(self):
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.cameraWidget)
        self.updateShape()
        self.update()

    def connectSignals(self):
        self.camera.newFrame.connect(self.screen.setImage)
        self.camera.shapeChanged.connect(self.updateShape)

    def updateShape(self):
        self.screen.updateShape(self.camera.shape)


def parse_command_line():
    import argparse

    parser = argparse.ArgumentParser()
    opt = dict(action='store_true')
    arg = parser.add_argument
    arg('-c', dest='opencv', help='OpenCV camera', **opt)
    arg('-s', dest='spinnaker', help='Spinnaker camera', **opt)
    return parser.parse_known_args()


def choose_camera(args):
    from QVideo.cameras.Noise import QNoiseWidget

    CameraWidget = QNoiseWidget
    if args.opencv:
        try:
            from QVideo.cameras.OpenCV import QOpenCVWidget
            CameraWidget = QOpenCVWidget
        except ImportError:
            print('Could not open OpenCV camera')
    elif args.spinnaker:
        try:
            from QVideo.cameras.Spinnaker import QSpinnakerWidget
            CameraWidget = QSpinnakerWidget
        except ImportError:
            print('Could not open Spinnaker camera')

    return CameraWidget


def main():
    from PyQt5.QtWidgets import QApplication
    import sys

    args, qtargs = parse_command_line()
    CameraWidget = choose_camera(args)

    app = QApplication(qtargs)
    widget = demo(CameraWidget)
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
