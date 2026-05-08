'''Real-time object detection with YOLO.

References
----------
Jocher, G., Chaurasia, A., & Qiu, J. (2023). Ultralytics YOLO.
https://github.com/ultralytics/ultralytics

Redmon, J., Divvala, S., Girshick, R., & Farhadi, A. (2016).
You only look once: Unified, real-time object detection.
Proceedings of the IEEE Conference on Computer Vision and Pattern
Recognition, 779-788. https://doi.org/10.1109/CVPR.2016.91
'''

from qtpy import QtCore, QtWidgets
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


__all__ = ['YOLOFilter', 'QYOLOFilter']


class YOLOFilter(AsyncVideoFilter):

    '''YOLO object-detection filter.

    Runs YOLO inference in a background thread so the GUI remains
    responsive even when inference is slower than the camera frame rate.
    Frames are dropped when the worker is busy rather than queued,
    preventing latency build-up.

    Parameters
    ----------
    model_name : str
        Name of the YOLO model weights file.  Default: ``'yolo11n.pt'``.
    passthrough : bool
        If ``True``, :meth:`process` returns the original frame.
        If ``False``, it returns the frame annotated with bounding boxes.
        Default: ``False``.

    Signals
    -------
    featuresReady(numpy.ndarray)
        Emitted from the worker thread after each detection with an
        ``(N, 4)`` array of bounding boxes in ``xyxy`` format.
        Connected slots receive it on the GUI thread via queued delivery.
    '''

    featuresReady = QtCore.Signal(np.ndarray)

    def __init__(self,
                 model_name: str = 'yolo11n.pt',
                 passthrough: bool = False) -> None:
        if YOLO is None:
            raise ImportError(
                'YOLO is required for YOLOFilter.'
                '\n\tInstall it with: pip install ultralytics'
                '\n\tSee https://docs.ultralytics.com/ '
                'for more information.')
        super().__init__()
        try:
            self.model = YOLO(model_name)
        except FileNotFoundError:
            self._cleanup()
            raise FileNotFoundError(
                f'YOLO model "{model_name}" not found.'
                '\n\tProvide the name of a pretrained ultralytics model'
                '\n\tor the full path to a custom YOLO weights file.'
                '\n\tSee https://docs.ultralytics.com/models/ '
                'for available pretrained models.')
        self._passthrough = passthrough

    def process(self, image: Image) -> Image:
        '''Run YOLO inference on *image*.

        Called in the background thread.  Emits :attr:`featuresReady`
        with detected bounding boxes; queued delivery ensures the
        connected slot runs on the GUI thread.

        Parameters
        ----------
        image : Image
            Input frame.

        Returns
        -------
        Image
            Original frame if :attr:`passthrough` is ``True``;
            otherwise the frame annotated with bounding boxes.
        '''
        results = self.model(image, verbose=False)
        boxes = results[0].boxes.xyxy.cpu().numpy()
        self.featuresReady.emit(boxes)
        return image if self._passthrough else results[0].plot()

    @property
    def passthrough(self) -> bool:
        '''Return the original frame instead of the annotated frame.'''
        return self._passthrough

    @passthrough.setter
    def passthrough(self, value: bool) -> None:
        self._passthrough = bool(value)


class QYOLOFilter(QVideoFilter):

    '''QVideoFilter wrapper for :class:`YOLOFilter`.'''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'YOLO Filter', YOLOFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._checkbox = QtWidgets.QCheckBox('Passthrough')
        self._layout.addWidget(self._checkbox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._checkbox.stateChanged.connect(self._setPassthrough)

    @QtCore.Slot(int)
    def _setPassthrough(self, state: int) -> None:
        self.filter.passthrough = state
