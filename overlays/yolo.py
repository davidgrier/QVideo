'''Real-time object detection overlay using YOLO.

References
----------
Jocher, G., Chaurasia, A., & Qiu, J. (2023). Ultralytics YOLO.
https://github.com/ultralytics/ultralytics

Redmon, J., Divvala, S., Girshick, R., & Farhadi, A. (2016).
You only look once: Unified, real-time object detection.
Proceedings of the IEEE Conference on Computer Vision and Pattern
Recognition, 779-788. https://doi.org/10.1109/CVPR.2016.91
'''

from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from QVideo.lib import QOverlayWidget
from QVideo.lib.videotypes import Image
import numpy as np
import logging

try:
    import pandas as pd
except ImportError:
    pd = None


logger = logging.getLogger(__name__)

__all__ = ['QYoloOverlay', 'QYoloWidget']


_importError = None
try:
    from ultralytics import YOLO
except Exception as ex:  # a broken installation raises more than ImportError
    YOLO = None
    _importError = ex


class _YoloWorker(QtCore.QObject):
    '''Runs YOLO object detection in a background thread.

    Parameters
    ----------
    model_name : str
        Name of the YOLO model weights file. Default: ``'yolo11n.pt'``.
    confidence : float
        Minimum confidence threshold for reported detections.
        Default: ``0.25``.

    Signals
    -------
    newData(object)
        Emitted after each detection with a :class:`pandas.DataFrame`
        containing columns ``x1``, ``y1``, ``x2``, ``y2``,
        ``confidence``, ``class``, and ``label``.
        ``None`` on error or when no objects are detected.
    '''

    newData = QtCore.Signal(object)

    def __init__(self,
                 model_name: str = 'yolo11n.pt',
                 confidence: float = 0.25) -> None:
        super().__init__()
        if pd is None:
            raise ImportError(
                'pandas is required for QYoloWidget.'
                '\n\tInstall it with: pip install pandas'
                '\n\tor: pip install "QVideo[overlays]"')
        if YOLO is None:
            raise ImportError(
                'ultralytics is required for QYoloWidget.'
                '\n\tInstall it with: pip install ultralytics'
                '\n\tSee https://docs.ultralytics.com/ for more information.'
            ) from _importError
        try:
            self.model = YOLO(model_name)
        except FileNotFoundError as err:
            raise FileNotFoundError(
                f'YOLO model "{model_name}" not found.'
                '\n\tProvide the name of a pretrained ultralytics model'
                '\n\tor the full path to a custom YOLO weights file.'
                '\n\tSee https://docs.ultralytics.com/models/ '
                'for available pretrained models.') from err
        self.confidence = confidence

    @QtCore.Slot(np.ndarray)
    def process(self, image: Image) -> None:
        '''Run YOLO detection on *image* and emit :attr:`newData`.

        Parameters
        ----------
        image : Image
            Video frame to analyze.
        '''
        try:
            results = self.model(image, verbose=False, conf=self.confidence)
            boxes = results[0].boxes
            if len(boxes) == 0:
                features = None
            else:
                xyxy = boxes.xyxy.cpu().numpy()
                conf = boxes.conf.cpu().numpy()
                cls = boxes.cls.cpu().numpy().astype(int)
                features = pd.DataFrame({
                    'x1': xyxy[:, 0],
                    'y1': xyxy[:, 1],
                    'x2': xyxy[:, 2],
                    'y2': xyxy[:, 3],
                    'confidence': conf,
                    'class': cls,
                    'label': [results[0].names[c] for c in cls],
                })
        except Exception as exc:
            logger.warning(f'YOLO detection failed: {exc}')
            features = None
        self.newData.emit(features)


class QYoloOverlay(pg.GraphicsObject):
    '''Bounding-box overlay that marks YOLO detected objects.

    A :class:`pyqtgraph.GraphicsObject` that draws axis-aligned
    bounding boxes over detected objects.  Add it to a
    :class:`~QVideo.lib.QVideoScreen.QVideoScreen` via
    ``screen.addOverlay(widget.overlay)``.
    '''

    def __init__(self) -> None:
        super().__init__()
        self._features = None
        self._pen = pg.mkPen('g', width=2)

    def boundingRect(self) -> QtCore.QRectF:
        return QtCore.QRectF(0, 0, 10000, 10000)

    def paint(self, painter: QtGui.QPainter, option, widget=None) -> None:
        '''Draw bounding boxes for all current detections.'''
        if self._features is None or len(self._features) == 0:
            return
        painter.setPen(self._pen)
        for _, row in self._features.iterrows():
            painter.drawRect(QtCore.QRectF(
                row['x1'], row['y1'],
                row['x2'] - row['x1'],
                row['y2'] - row['y1']))

    @QtCore.Slot(object)
    def setFeatures(self, features) -> None:
        '''Update bounding boxes from a YOLO detections DataFrame.

        Parameters
        ----------
        features : pandas.DataFrame or None
            DataFrame with ``x1``, ``y1``, ``x2``, ``y2`` columns
            returned by :class:`_YoloWorker`.  ``None`` or empty clears
            the overlay.
        '''
        self._features = features
        self.update()


class QYoloWidget(QOverlayWidget):
    '''Control widget for the YOLO object-detection overlay.

    Runs YOLO inference in a background thread and renders detected
    object bounding boxes as a :class:`QYoloOverlay` on a
    :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.

    Use ``screen.addOverlay(widget.overlay)`` to register the overlay
    graphics item with a screen, and set :attr:`source` to supply video frames.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    model_name : str
        YOLO model weights file. Default: ``'yolo11n.pt'``.
    confidence : float
        Initial confidence threshold. Default: ``0.25``.

    '''

    def __init__(self,
                 parent: QtWidgets.QWidget | None = None,
                 model_name: str = 'yolo11n.pt',
                 confidence: float = 0.25) -> None:
        worker = _YoloWorker(model_name=model_name, confidence=confidence)
        super().__init__('YOLO', QYoloOverlay(), worker, parent)

    def _setupUi(self) -> None:
        super()._setupUi()
        self._confidenceSpinBox = QtWidgets.QDoubleSpinBox()
        self._confidenceSpinBox.setRange(0., 1.)
        self._confidenceSpinBox.setSingleStep(0.05)
        self._confidenceSpinBox.setDecimals(2)
        self._confidenceSpinBox.setValue(self._worker.confidence)
        self._confidenceSpinBox.valueChanged.connect(self._setConfidence)
        self._layout.addRow('Confidence', self._confidenceSpinBox)

    @QtCore.Slot(float)
    def _setConfidence(self, value: float) -> None:
        self._worker.confidence = value
