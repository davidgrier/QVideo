from PyQt5.QtWidgets import (QWidget, QHBoxLayout)
from PyQt5.QtCore import QEvent
from QVideo.lib import QVideoScreen

from QVideo.filters.SampleHold import SampleHold

import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class demo(QWidget):

    def __init__(self, QCameraWidget, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.screen = QVideoScreen(self)

        self.screen.filter.register(SampleHold(order=3))

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


def parse_command_line():
    import argparse

    parser = argparse.ArgumentParser()
    opt = dict(action='store_true')
    arg = parser.add_argument
    arg('-c', dest='opencv', help='OpenCV camera', **opt)
    arg('-s', dest='spinnaker', help='Spinnaker camera', **opt)
    return parser.parse_known_args()


def choose_camera(args):
    if args.opencv:
        try:
            from QVideo.cameras.OpenCV import QOpenCVTree as QOpenCVWidget
            return QOpenCVWidget
        except ImportError as ex:
            logger.warning(f'Could not import OpenCV camera: {ex}')
    if args.spinnaker:
        try:
            from QVideo.cameras.Spinnaker import QSpinnakerWidget
            return QSpinnakerWidget
        except ImportError as ex:
            logger.warning(f'Could not import Spinnaker camera: {ex}')
    from QVideo.cameras.Noise import QNoiseTree as QNoiseWidget
    return QNoiseWidget


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
