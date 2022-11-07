from PyQt5.QtWidgets import QWidget
from PyQt5 import uic
from PyQt5.QtCore import pyqtSlot
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


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

    def closeEvent(self, event) -> None:
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
    widget = QBasicDVR(cameraWidget=CameraWidget())
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
