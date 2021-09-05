from QVideo.lib import QCameraWidget
from QVideo.cameras.Noise.QNoiseSource import QNoiseSource


class QNoiseWidget(QCameraWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args,
                         camera=QNoiseSource(),
                         uiFile='QNoiseWidget.ui',
                         **kwargs)
        self.camera.fpsReady.connect(self.ui.rate.setValue)


def main():
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = QNoiseWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
