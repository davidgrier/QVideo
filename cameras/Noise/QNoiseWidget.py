from QVideo.lib import QCameraTree
from QVideo.cameras.Noise.QNoiseSource import QNoiseSource


class QNoiseWidget(QCameraTree):

    UIFILE = 'QNoiseWidget.ui'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args,
                         camera=QNoiseSource(),
                         uiFile=self.UIFILE,
                         **kwargs)
        self.camera.meter.fpsReady.connect(self.ui.rate.setValue)


def example() -> None:
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = QNoiseWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    example()
