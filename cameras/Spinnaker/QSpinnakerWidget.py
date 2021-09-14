from QVideo.lib import QCameraWidget
from QSpinnakerCamera import QSpinnakerCamera


class QSpinnakerWidget(QCameraWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args,
                         camera=QSpinnakerCamera(),
                         uiFile='QSpinnakerWidget.ui',
                         **kwargs)
        self.setRanges()
        self.connectSignals()

    def setRanges(self):
        cam = self.camera
        self.ui.acquisitionframerate.setRange(*cam.acquisitionframeraterange)
        self.ui.exposuretime.setRange(*cam.exposuretimerange)
        self.ui.gain.setRange(*cam.gainrange)
        self.ui.gamma.setRange(*cam.gammarange)
        self.ui.height.setRange(*cam.heightrange)
        self.ui.offsetx.setRange(*cam.offsetxrange)
        self.ui.offsety.setRange(*cam.offsetyrange)
        self.ui.width.setRange(*cam.widthrange)
        self.update()

    def connectSignals(self):
        self.camera.fpsReady.connect(self.ui.actualrate.setValue)


def main():
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = QSpinnakerWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
