from QVideo.lib import QCamera
from PyQt5.QtCore import pyqtProperty
import cv2
from typing import Optional
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QOpenCVCamera(QCamera):
    '''OpenCV camera

    Uses the VideoCapture interface from the OpenCV project to
    open a digital camera, set and get its properties, and
    capture images.
    .....

    Properties
    ----------

    Methods
    -------
    read(): bool, np.ndarray
        Returns a tuple (success, image):
        success: bool
            True if image capture was successful
        image: numpy.ndarray
    '''

    if cv2.__version__.startswith('2.'):
        WIDTH = cv2.cv.CV_CAP_PROP_FRAME_WIDTH
        HEIGHT = cv2.cv.CV_CAP_PROP_FRAME_HEIGHT
        BGR2RGB = cv2.cv.CV_BGR2RGB
        BGR2GRAY = cv2.cv.CV_BGR2GRAY
        FPS = cv2.cv.CV_CAP_PROP_FPS
    else:
        WIDTH = cv2.CAP_PROP_FRAME_WIDTH
        HEIGHT = cv2.CAP_PROP_FRAME_HEIGHT
        BGR2RGB = cv2.COLOR_BGR2RGB
        BGR2GRAY = cv2.COLOR_BGR2GRAY
        FPS = cv2.CAP_PROP_FPS
    conversion = {True: BGR2GRAY, False: BGR2RGB}

    def Property(ptype, name: str):

        def getter(inst) -> ptype:
            return getattr(inst, f'_{name}')

        def setter(inst, value: ptype):
            setattr(inst, f'_{name}', value)

        return pyqtProperty(ptype, getter, setter)

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
        self.cameraID = cameraID
        self.open()
        self.mirrored = mirrored
        self.flipped = flipped
        self.gray = gray

    def _initialize(self) -> bool:
        self.device = cv2.VideoCapture(self.cameraID)
        for _ in range(5):
            if (ready := self.device.read()[0]):
                break
        return ready

    def _deinitialize(self) -> None:
        self.device.release()

    def read(self) -> QCamera.CameraData:
        if self.isOpen():
            ready, image = self.device.read()
        else:
            ready, image = False, None
        if ready:
            if image.ndim == 3:
                image = cv2.cvtColor(image, self.conversion[self.gray])
            if self.flipped or self.mirrored:
                operation = self.mirrored * (1 - 2*self.flipped)
                image = cv2.flip(image, operation)
        return ready, image

    @pyqtProperty(int)
    def width(self):
        return int(self.device.get(self.WIDTH))

    @width.setter
    def width(self, value):
        self.device.set(self.WIDTH, value)
        self.shapeChanged.emit(self.shape)

    @pyqtProperty(int)
    def height(self):
        return int(self.device.get(self.HEIGHT))

    @height.setter
    def height(self, value):
        self.device.set(self.HEIGHT, value)
        self.shapeChanged.emit(self.shape)

    @pyqtProperty(float)
    def fps(self) -> float:
        return int(self.device.get(self.FPS))

    @fps.setter
    def fps(self, value):
        self.device.set(self.FPS, value)


def example() -> None:
    from QVideo.lib import QVideoCamera
    from pprint import pprint

    logger.setLevel(logging.ERROR)

    camera = QOpenCVCamera()
    print(camera.name)
    pprint(camera.settings())
    with camera:
        for n in range(5):
            print('.' if camera.read()[0] else 'x', end='')
        else:
            print('done')
    with camera:
        for n in range(5):
            print('.' if camera.read()[0] else 'x', end='')
        else:
            print('done')


if __name__ == '__main__':
    example()
