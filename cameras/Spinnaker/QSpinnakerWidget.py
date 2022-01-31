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
        self.ui.gray.setEnabled(self.camera.colorCapable())
        self.setRanges()
        self.connectSignals()

    def setRange(self, name):
        prop = getattr(self.camera.device, name)
        try:
            step = prop.GetInc()
        except:
            step = 0
        logger.debug(f'Setting Range: {name}: ({prop.GetMin()}, {prop.GetMax()}, {step})')
        widget = getattr(self.ui, name.lower())
        dtype = float if 'Double' in type(widget).__name__ else int
        widget.setRange(dtype(prop.GetMin()), dtype(prop.GetMax()))
        if step != 0:
            widget.setSingleStep(step)

    def setRanges(self):
        self.setRange('AcquisitionFrameRate')
        self.setRange('BlackLevel')
        self.setRange('ExposureTime')
        self.setRange('Gain')
        self.setRange('Gamma')
        self.setRange('Height')
        self.setRange('OffsetX')
        self.setRange('OffsetY')
        self.setRange('Width')
        self.update()

    def connectSignals(self):
        self.camera.meter.fpsReady.connect(self.ui.actualrate.setValue)
        self.camera.propertyChanged.connect(self.changeHandler)

    @pyqtSlot(str)
    def changeHandler(self, name):
        logger.debug(f'Changed: {name}')
        if 'auto' in name:
            self._syncProperties()
        self.setRanges()


def main():
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = QSpinnakerWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
