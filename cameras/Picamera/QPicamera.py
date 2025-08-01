from QVideo.lib import QCamera
from pyqtgraph.Qt.QtCore import pyqtProperty
import time
import logging
try:
    from picamera2 import Picamera2
except (ImportError, ModuleNotFoundError) as error:
    Picamera2 = None


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class QPicamera(QCamera):
    '''Support for Raspberry Pi cameras

    '''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.open()

    def _initialize(self) -> bool:
        if Picamera2 is None:
            logger.warning('''
            Could not import picamera2 library:
            Raspberry Pi camera is not available''')
            return False
        self.device = Picamera2()
        self.device.start()
        time.sleep(1)
        return True

    def _deinitialize(self) -> bool:
        self.device.stop()

    def read(self) -> QCamera.CameraData:
        if not self.isOpen():
            return False, None
        frame = self.device.capture_array()
        return True, frame


if __name__ == '__main__':
    QPicamera.example()
