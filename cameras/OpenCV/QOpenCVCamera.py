from QVideo.lib import QVideoCamera
from PyQt5.QtCore import pyqtProperty
import cv2
import time
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QOpenCVCamera(QVideoCamera):
    '''OpenCV camera

    Attributes
    ----------

    Methods
    -------
    read():
        Returns image as numpy.ndarray

    '''

    if cv2.__version__.startswith('2.'):
        WIDTH = cv2.cv.CV_CAP_PROP_FRAME_WIDTH
        HEIGHT = cv2.cv.CV_CAP_PROP_FRAME_HEIGHT
        BGR2RGB = cv2.cv.CV_BGR2RGB
        BGR2GRAY = cv2.cv.CV_BGR2GRAY
    else:
        WIDTH = cv2.CAP_PROP_FRAME_WIDTH
        HEIGHT = cv2.CAP_PROP_FRAME_HEIGHT
        BGR2RGB = cv2.COLOR_BGR2RGB
        BGR2GRAY = cv2.COLOR_BGR2GRAY

    def Dimension(propid):
        def getter(self):
            return self.device.get(propid)

        def setter(self, value):
            logger.debug(f'Setting dimension {propid}: {value}')
            self.device.set(propid, value)
            self.shapeChanged.emit()
        return pyqtProperty(int, getter, setter)

    width = Dimension(WIDTH)
    height = Dimension(HEIGHT)

    def __init__(self, *args,
                 cameraID=0,
                 mirrored=False,
                 flipped=False,
                 gray=False,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.device = cv2.VideoCapture(cameraID)

        # camera properties
        self.mirrored = mirrored
        self.flipped = flipped
        self.gray = gray

        # initialize camera with one frame
        while True:
            ready, image = self.read()
            if ready:
                break

    def read(self):
        ready, image = self.device.read()
        if not ready:
            time.sleep(0.01)
            return ready, None
        if image.ndim == 3:
            image = cv2.cvtColor(image, self._conversion)
        if self.flipped or self.mirrored:
            image = cv2.flip(image, self.mirrored * (1 - 2 * self.flipped))
        return ready, image

    def close(self):
        logger.debug('Closing')
        self.device.release()

    # Camera properties

    @pyqtProperty(bool)
    def mirrored(self):
        return self._mirrored

    @mirrored.setter
    def mirrored(self, value):
        self._mirrored = value

    @pyqtProperty(bool)
    def flipped(self):
        return self._flipped

    @flipped.setter
    def flipped(self, value):
        self._flipped = value

    @pyqtProperty(bool)
    def gray(self):
        gray = (self._conversion == self.BGR2GRAY)
        logger.debug(f'Getting gray: {gray}')
        return gray

    @gray.setter
    def gray(self, gray):
        logger.debug(f'Setting gray: {gray}')
        self._conversion = self.BGR2GRAY if gray else self.BGR2RGB
