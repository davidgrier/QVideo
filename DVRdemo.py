from PyQt5.QtWidgets import QWidget
from PyQt5 import uic
from PyQt5.QtCore import pyqtSlot


class DVRdemo(QWidget):

    def __init__(self, *args, cameraWidget=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cameraWidget = cameraWidget
        self.camera = cameraWidget.camera
        self.setupUi()
        self.connectSignals()

    def setupUi(self):
        uic.loadUi('DVRdemo.ui', self)
        self.controls.layout().addWidget(self.cameraWidget)
        self.updateShape()

    def connectSignals(self):
        self.dvr.source = self.camera
        self.camera.newFrame.connect(self.screen.setImage)
        self.camera.shapeChanged.connect(self.updateShape)
        self.dvr.playing.connect(self.dvrPlayback)

    def updateShape(self):
        self.screen.updateShape(self.camera.shape)

    @pyqtSlot(bool)
    def dvrPlayback(self, playback):
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
    from QVideo.cameras.Noise import QNoiseTree as QNoiseWidget
    try:
        from QVideo.cameras.OpenCV import QOpenCVTree as QOpenCVWidget
        have_opencv = True
    except ImportError:
        have_opencv = False
    try:
        from QVideo.cameras.Spinnaker import QSpinnakerWidget
        have_spinnaker = True
    except ImportError:
        have_spinnaker = False

    if have_opencv and args.opencv:
        return QOpenCVWidget
    elif have_spinnaker and args.spinnaker:
        return QSpinnakerWidget
    return QNoiseWidget


def main():
    from PyQt5.QtWidgets import QApplication
    import sys

    args, qtargs = parse_command_line()
    CameraWidget = choose_camera(args)

    app = QApplication(qtargs)
    widget = DVRdemo(cameraWidget=CameraWidget())
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
