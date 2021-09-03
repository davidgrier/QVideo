from QCameraWidget import QCameraWidget
from QSpinnakerCamera import QSpinnakerCamera


class QSpinnakerWidget(QCameraWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args,
                         camera=QSpinnakerCamera(),
                         uiFile='QSpinakerWidget.ui',
                         **kwargs)
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
