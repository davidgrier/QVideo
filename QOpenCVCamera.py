from QVideoCamera import QVideoCamera
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

    def __init__(self, *args,
                 cameraID=0,
                 mirrored=False,
                 flipped=False,
                 gray=False,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.device = cv2.VideoCapture(cameraID)

        if cv2.__version__.startswith('2.'):
            self._WIDTH = cv2.cv.CV_CAP_PROP_FRAME_WIDTH
            self._HEIGHT = cv2.cv.CV_CAP_PROP_FRAME_HEIGHT
            self._toRGB = cv2.cv.CV_BGR2RGB
            self._toGRAY = cv2.cv.CV_BGR2GRAY
        else:
            self._WIDTH = cv2.CAP_PROP_FRAME_WIDTH
            self._HEIGHT = cv2.CAP_PROP_FRAME_HEIGHT
            self._toRGB = cv2.COLOR_BGR2RGB
            self._toGRAY = cv2.COLOR_BGR2GRAY

        # camera properties
        self.mirrored = bool(mirrored)
        self.flipped = bool(flipped)
        self.gray = bool(gray)

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
    @pyqtProperty(int)
    def width(self):
        return int(self.device.get(self._WIDTH))

    @width.setter
    def width(self, width):
        self.device.set(self._WIDTH, width)
        logger.info(f'Setting camera width: {width}')

    @pyqtProperty(int)
    def height(self):
        return int(self.device.get(self._HEIGHT))

    @height.setter
    def height(self, height):
        self.device.set(self._HEIGHT, height)
        logger.info(f'Setting camera height: {height}')

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
        gray = self._conversion == self._toGRAY
        logger.debug(f'Getting gray: {gray}')
        return gray

    @gray.setter
    def gray(self, gray):
        logger.debug(f'Setting gray: {gray}')
        self._conversion = self._toGRAY if gray else self._toRGB
