from QVideo.lib import QCameraWidget
from QVideo.cameras.Spinnaker.QSpinnakerCamera import QSpinnakerCamera
from PyQt5.QtCore import pyqtSlot
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QSpinnakerWidget(QCameraWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args,
                         camera=QSpinnakerCamera(),
                         uiFile='QSpinnakerWidget.ui',
                         **kwargs)
        self.setRanges()
        self.connectSignals()

    def setRange(self, name):
        set = getattr(self.ui, name).setRange
        range = getattr(self.camera, name+'range')
        logger.debug(f'Setting Range: {name}: {range}')
        set(*range)

    def setRanges(self):
        self.setRange('acquisitionframerate')
        self.setRange('exposuretime')
        self.setRange('gain')
        self.setRange('gamma')
        self.setRange('height')
        self.setRange('offsetx')
        self.setRange('offsety')
        self.setRange('width')
        self.update()

    def connectSignals(self):
        self.camera.fpsReady.connect(self.ui.actualrate.setValue)
        self.camera.propertyChanged.connect(self.changeHandler)

    @pyqtSlot(str)
    def changeHandler(self, name):
        logger.debug(f'Changed: {name}')


def main():
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = QSpinnakerWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
