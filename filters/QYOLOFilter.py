from pyqtgraph.Qt import QtCore, QtWidgets
from QVideo.lib.VideoFilter import QVideoFilter, VideoFilter
from QVideo.lib.types import Image
from ultralytics import YOLO


__all__ = ['YOLOFilter', 'QYOLOFilter']


class YOLOFilter(VideoFilter):

    '''YOLO object detection filter.

    Parameters
    ----------
    model_name : str
        Name of the YOLO model weights file.
        Default: ``'yolov8n.pt'``.
    '''

    def __init__(self, model_name: str = 'yolov8n.pt') -> None:
        super().__init__()
        self.model = YOLO(model_name)

    def get(self) -> Image | None:
        '''Return the most recently added frame with YOLO detections.

        Returns
        -------
        Image or None
            The most recently added frame with YOLO detections drawn on it,
            or ``None`` if no frame has been added yet.
        '''
        if self.data is None:
            return None
        results = self.model(self.data, verbose=False)
        return results[0].plot()


class QYOLOFilter(QVideoFilter):

    '''QVideoFilter wrapper for YOLOFilter.'''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__('YOLO Filter', parent, YOLOFilter())
