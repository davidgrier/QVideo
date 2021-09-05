from PyQt5.QtWidgets import (QWidget, QHBoxLayout)
from QVideo.lib import QVideoScreen
from QVideo.cameras.Noise import QNoiseWidget

try:
    from QVideo.cameras.OpenCV import QOpenCVWidget
    have_opencv = True
except ImportError:
    have_opencv = False

try:
    from QVideo.cameras.Spinnaker import QSpinnakerWidget
    have_spinnaker = True
except ImportError:
    have_spinnaker = False


class demo(QWidget):

    def __init__(self, QCameraWidget):
        super().__init__()
        self.source = QCameraWidget(self)
        self.screen = QVideoScreen(self, source=self.source.camera)
        self.setupUi()

    def setupUi(self):
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.source)
        self.update()


def main():
    from PyQt5.QtWidgets import QApplication
    import sys
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    opt = dict(action='store_true')
    arg = parser.add_argument
    arg('-c', dest='opencv', help='OpenCV camera', **opt)
    arg('-s', dest='spinnaker', help='Spinnaker camera', **opt)
    args, qtargs = parser.parse_known_args()

    # Select camera
    if have_opencv and args.opencv:
        Camera = QOpenCVWidget
    elif have_spinnaker and args.spinnaker:
        Camera = QSpinnakerWidget
    else:
        Camera = QNoiseWidget

    # Run demo
    app = QApplication(qtargs)
    widget = demo(Camera)
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
