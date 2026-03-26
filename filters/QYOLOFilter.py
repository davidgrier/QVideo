'''Real-time object detection with YOLO.

References
----------
.. [1] Jocher, G., Chaurasia, A., & Qiu, J. (2023). Ultralytics YOLO.
   https://github.com/ultralytics/ultralytics

.. [2] Redmon, J., Divvala, S., Girshick, R., & Farhadi, A. (2016).
   You only look once: Unified, real-time object detection.
   Proceedings of the IEEE Conference on Computer Vision and Pattern
   Recognition, 779-788. https://doi.org/10.1109/CVPR.2016.91
'''

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
        Default: ``'yolo11n.pt'``.
    passthrough: bool
        If True, return the input image.
        If False, mark up the image with bounding box data
    '''

    #: Emitted with bounding boxes of detected features.
    featuresReady = QtCore.pyqtSignal(np.ndarray)

    def __init__(self,
                 model_name: str = 'yolo11n.pt',
                 passthrough: bool = False) -> None:
        super().__init__()
        if YOLO is None:
            raise ImportError(
                'YOLO is required for QYOLOFilter.'
                '\n\tInstall it with: pip install ultralytics'
                '\n\tSee https://docs.ultralytics.com/ '
                'for more information.')
        try:
            self.model = YOLO(model_name)
        except FileNotFoundError:
            raise FileNotFoundError(
                f'YOLO model "{model_name}" not found.'
                '\n\tProvide the name of a pretrained ultralytics model'
                '\n\tor the full path to a custom YOLO weights file.'
                '\n\tSee https://docs.ultralytics.com/models/ '
                'for available pretrained models.')
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
