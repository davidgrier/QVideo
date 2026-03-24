'''Real-time object detection with YOLO.'''

from pyqtgraph.Qt import QtCore, QtWidgets
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.types import Image
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


__all__ = ['YOLOFilter', 'QYOLOFilter']


class YOLOFilter(VideoFilter):

    '''YOLO object detection filter.

    Parameters
    ----------
    model_name: str
        Name of the YOLO model weights file.
        Default: ``'yolov8n.pt'``.
    passthrough: bool
        If True, return the input image.
        If False, mark up the image with bounding box data

    Signals
    -------
    featuresReady: pandas.DataFrame
        Bounding boxes of YOLO detections
    '''

    featuresReady = QtCore.pyqtSignal(np.ndarray)

    def __init__(self,
                 model_name: str = 'yolov8n.pt',
                 passthrough: bool = False) -> None:
        super().__init__()
        if YOLO is None:
            raise ImportError(
                'YOLO is required for QYOLOFilter. '
                'Install it with: pip install ultralytics')
        self.model = YOLO(model_name)
        self._passthrough = passthrough

    def add(self, image: Image) -> None:
        '''Performs YOLO feature detection on image

        Emits featuresReady with bounding-box data
        '''
        results = self.model(image, verbose=False)
        boxes = results[0].boxes.xyxy.numpy()
        self.featuresReady.emit(boxes)
        self.data = image if self._passthrough else results[0].plot()

    @property
    def passthrough(self) -> bool:
        return self._passthrough

    @passthrough.setter
    def passthrough(self, value: bool) -> None:
        self._passthrough = bool(value)


class QYOLOFilter(QVideoFilter):

    '''QVideoFilter wrapper for YOLOFilter.'''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'YOLO Filter', YOLOFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._checkbox = QtWidgets.QCheckBox('Passthrough')
        self._layout.addWidget(self._checkbox)
        self._checkbox.stateChanged.connect(self._setPassthrough)

    @QtCore.pyqtSlot(int)
    def _setPassthrough(self, state: int) -> None:
        self.filter.passthrough = state
