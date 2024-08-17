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
    conversion = {True: BGR2GRAY, False: BGR2RGB}

    def Property(dtype, prop):
        return pyqtProperty(dtype,
                            lambda self: getattr(self, f'_{prop}'),
                            lambda self, v: setattr(self, f'_{prop}', v))

    mirrored = Property(bool, 'mirrored')
    flipped = Property(bool, 'flipped')
    gray = Property(bool, 'gray')

    def __init__(self, *args,
                 cameraID: int = 0,
                 mirrored: bool = False,
                 flipped: bool = False,
                 gray: bool = False,
                 **kwargs) -> None:
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
            image = cv2.cvtColor(image, self.conversion[self.gray])
        if self.flipped or self.mirrored:
            image = cv2.flip(image, self.mirrored * (1 - 2 * self.flipped))
        return ready, image

    def close(self):
        logger.debug('Closing')
        super().close()
        self.device.release()

    @pyqtProperty(int)
    def width(self):
        return self.device.get(self.WIDTH)

    @width.setter
    def width(self, value):
        self.device.set(self.WIDTH, value)
        self.shapeChanged.emit()

    @pyqtProperty(int)
    def height(self):
        return self.device.get(self.HEIGHT)

    @height.setter
    def height(self, value):
        self.device.set(self.HEIGHT, value)
        self.shapeChanged.emit()
