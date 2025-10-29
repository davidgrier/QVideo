from QVideo.lib import QCamera
from pyqtgraph.Qt.QtCore import pyqtProperty
import cv2
import platform
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QOpenCVCamera(QCamera):
    '''
    Camera class that uses OpenCV to access a camera device.

    Inherits
    -------
    QVideo.lib.QCamera

    Parameters
    ----------
    cameraID : int
        ID of the camera device (default is 0).
    mirrored : bool
        If True, the image is mirrored horizontally.
    flipped : bool
        If True, the image is flipped vertically.
    gray : bool
        If True, the image is converted to grayscale.

    Attributes
    ----------
    width : int
        Width of the camera frame.
    height : int
        Height of the camera frame.
    fps : float
        Frames per second of the camera.

    Methods
    -------
    read() -> QCamera.CameraData
        Reads a frame from the camera and applies transformations.
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
        system = platform.system()
        if system == 'Linux':
            api = cv2.CAP_V4L2
        else:
            api = cv2.CAP_ANY
        self.device = cv2.VideoCapture(self.cameraID, api)
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
    def width(self) -> int:
        return int(self.device.get(self.WIDTH))

    @width.setter
    def width(self, value: int) -> None:
        self.device.set(self.WIDTH, value)
        self.shapeChanged.emit(self.shape)

    @pyqtProperty(int)
    def height(self) -> int:
        return int(self.device.get(self.HEIGHT))

    @height.setter
    def height(self, value: int) -> None:
        self.device.set(self.HEIGHT, value)
        self.shapeChanged.emit(self.shape)

    @pyqtProperty(float)
    def fps(self) -> float:
        return int(self.device.get(self.FPS))

    @fps.setter
    def fps(self, value: float) -> None:
        self.device.set(self.FPS, value)


if __name__ == '__main__':
    QOpenCVCamera.example()
