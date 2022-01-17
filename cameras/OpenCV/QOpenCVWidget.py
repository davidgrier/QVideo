from QVideo.lib import QCameraWidget
from QVideo.cameras.OpenCV.QOpenCVCamera import QOpenCVCamera


class QOpenCVWidget(QCameraWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args,
                         camera=QOpenCVCamera(),
                         uiFile='QOpenCVWidget.ui',
                         **kwargs)
        self.camera.meter.fpsReady.connect(self.ui.rate.setValue)


def main():
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = QOpenCVWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
