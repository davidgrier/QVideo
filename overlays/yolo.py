'''Real-time object detection overlay using YOLO.

Two backends run the network.  ``ultralytics`` (and so ``torch``) loads a
``.pt`` file and can use a GPU.  OpenCV loads an ``.onnx`` export and needs
nothing beyond QVideo; it runs on the CPU.  ``backend='auto'`` chooses by the
extension of the model file.  See the documentation of the overlays for how
to prepare an ONNX file.

References
----------
Jocher, G., Chaurasia, A., & Qiu, J. (2023). Ultralytics YOLO.
https://github.com/ultralytics/ultralytics

Redmon, J., Divvala, S., Girshick, R., & Farhadi, A. (2016).
You only look once: Unified, real-time object detection.
Proceedings of the IEEE Conference on Computer Vision and Pattern
Recognition, 779-788. https://doi.org/10.1109/CVPR.2016.91
'''

from collections.abc import Sequence
from qtpy import QtCore, QtGui, QtWidgets
import cv2
import pyqtgraph as pg
from QVideo.lib import QOverlayWidget
from QVideo.lib.dnn import DNN, letterbox, prepare
from QVideo.lib.videotypes import Image
import numpy as np
import logging

try:
    import pandas as pd
except ImportError:
    pd = None


logger = logging.getLogger(__name__)

__all__ = ['QYoloOverlay', 'QYoloWidget', 'decode', 'COCO_NAMES']


_importError = None
try:
    from ultralytics import YOLO
except Exception as ex:  # a broken installation raises more than ImportError
    YOLO = None
    _importError = ex


#: The names of the 80 classes of the COCO data set, which the pretrained
#: YOLO networks detect.
COCO_NAMES = (
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train',
    'truck', 'boat', 'traffic light', 'fire hydrant', 'stop sign',
    'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard',
    'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard',
    'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup', 'fork',
    'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
    'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv',
    'laptop', 'mouse', 'remote', 'keyboard', 'cell phone', 'microwave',
    'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase',
    'scissors', 'teddy bear', 'hair drier', 'toothbrush')


def decode(output: np.ndarray,
           confidence: float,
           iou: float = 0.45,
           scale: float = 1.,
           pad: tuple[float, float] = (0., 0.),
           shape: tuple[int, int] | None = None,
           transposed: bool = False
           ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    '''Turn the output of a YOLO network into boxes.

    The layout is that of the ONNX export of Ultralytics YOLOv8 and later
    detection models: ``(1, 4 + nc, N)``, where each of the *N* candidates
    has the center ``x, y`` and the size ``w, h`` of its box in the pixels
    of the network input, followed by a score for each of the *nc* classes.
    There is no separate objectness, as in YOLOv5, and the candidates are
    not yet reduced by non-maximum suppression, which this function does.
    An export of the shape ``(1, N, 4 + nc)`` is read with *transposed*.

    Parameters
    ----------
    output : numpy.ndarray
        The output of the network for one image.
    confidence : float
        Candidates whose best class scores less are dropped.
    iou : float
        Of two overlapping boxes, the one with the lower score is dropped
        if the intersection over the union passes this.
    scale, pad :
        As :func:`~QVideo.lib.dnn.letterbox` returns them, to give the boxes
        in the pixels of the original image.
    shape : tuple of int, optional
        ``(height, width)`` of the original image, to which the boxes are
        clipped.
    transposed : bool
        The output is ``(1, N, 4 + nc)``.  There is no telling the layouts
        apart by their shapes when *N* is small, so the default is the
        standard export, ``(1, 4 + nc, N)``.

    Returns
    -------
    boxes : numpy.ndarray
        ``(n, 4)`` array of ``x1, y1, x2, y2``.
    scores : numpy.ndarray
        The score of each box.
    classes : numpy.ndarray
        The class of each box, an integer.
    '''
    candidates = np.squeeze(output, axis=0) if output.ndim == 3 else output
    if not transposed:
        candidates = candidates.T                 # (N, 4 + nc)
    scores = candidates[:, 4:]
    classes = scores.argmax(axis=1)
    best = scores[np.arange(len(scores)), classes]
    keep = best >= confidence
    candidates, classes, best = candidates[keep], classes[keep], best[keep]
    if len(best) == 0:
        return (np.empty((0, 4), np.float32), np.empty(0, np.float32),
                np.empty(0, int))
    cx, cy, w, h = candidates[:, :4].T
    boxes = np.stack([cx - w / 2, cy - h / 2, w, h], axis=1)  # x, y, w, h
    chosen = np.asarray(cv2.dnn.NMSBoxes(
        boxes.tolist(), best.tolist(), confidence, iou)).reshape(-1)
    boxes, best, classes = boxes[chosen], best[chosen], classes[chosen]
    xyxy = np.stack([boxes[:, 0], boxes[:, 1],
                     boxes[:, 0] + boxes[:, 2],
                     boxes[:, 1] + boxes[:, 3]], axis=1)
    xyxy = (xyxy - (pad[0], pad[1], pad[0], pad[1])) / scale
    if shape is not None:
        height, width = shape
        xyxy[:, [0, 2]] = xyxy[:, [0, 2]].clip(0, width)
        xyxy[:, [1, 3]] = xyxy[:, [1, 3]].clip(0, height)
    return xyxy, best, classes


class _YoloWorker(QtCore.QObject):
    '''Runs YOLO object detection in a background thread.

    Parameters
    ----------
    model_name : str
        Name of the YOLO model weights file. Default: ``'yolo11n.pt'``.
    confidence : float
        Minimum confidence threshold for reported detections.
        Default: ``0.25``.
    backend : {'auto', 'ultralytics', 'opencv'}
        What runs the network.  ``'auto'`` uses OpenCV for a ``.onnx`` file
        and ``ultralytics`` for anything else.
    imgsz : int
        Side of the square input of the network, for the OpenCV backend;
        the size at which the model was exported.  Default: ``640``.
    names : sequence of str or None
        The name of each class, for the OpenCV backend.  The default is
        the 80 names of COCO if the network has 80 classes, and the number
        of the class otherwise.

    Signals
    -------
    newData(object)
        Emitted after each detection with a :class:`pandas.DataFrame`
        containing columns ``x1``, ``y1``, ``x2``, ``y2``,
        ``confidence``, ``class``, and ``label``.
        ``None`` on error or when no objects are detected.
    '''

    newData = QtCore.Signal(object)

    #: Intersection over union above which overlapping boxes are merged.
    iou = 0.45

    def __init__(self,
                 model_name: str = 'yolo11n.pt',
                 confidence: float = 0.25,
                 backend: str = 'auto',
                 imgsz: int = 640,
                 names: Sequence[str] | None = None) -> None:
        super().__init__()
        if backend == 'auto':
            backend = ('opencv' if str(model_name).lower().endswith('.onnx')
                       else 'ultralytics')
        if backend not in ('ultralytics', 'opencv'):
            raise ValueError(f'Unknown YOLO backend {backend!r}: '
                             "use 'auto', 'ultralytics' or 'opencv'")
        if pd is None:
            raise ImportError(
                'pandas is required for QYoloWidget.'
                '\n\tInstall it with: pip install pandas'
                '\n\tor: pip install "QVideo[overlays]"')
        self.backend = backend
        self.confidence = confidence
        self.imgsz = imgsz
        self.names = names
        if backend == 'opencv':
            self.model = DNN(model_name, size=(imgsz, imgsz))
            return
        if YOLO is None:
            raise ImportError(
                'ultralytics is required for QYoloWidget.'
                '\n\tInstall it with: pip install ultralytics'
                '\n\tSee https://docs.ultralytics.com/ for more information.'
                "\n\tOr use an ONNX file, which OpenCV runs: "
                "backend='opencv'."
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

    @QtCore.Slot(np.ndarray)
    def process(self, image: Image) -> None:
        '''Run YOLO detection on *image* and emit :attr:`newData`.

        Parameters
        ----------
        image : Image
            Video frame to analyze.
        '''
        try:
            if self.backend == 'opencv':
                features = self._detectOpenCV(image)
            else:
                features = self._detectUltralytics(image)
        except Exception as exc:
            logger.warning(f'YOLO detection failed: {exc}')
            features = None
        self.newData.emit(features)

    def _detectUltralytics(self, image: Image):
        '''Return the detections of *image* by ultralytics, or ``None``.'''
        results = self.model(image, verbose=False, conf=self.confidence)
        boxes = results[0].boxes
        if len(boxes) == 0:
            return None
        xyxy = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        return self._features(xyxy, conf, cls,
                              [results[0].names[c] for c in cls])

    def _detectOpenCV(self, image: Image):
        '''Return the detections of *image* by OpenCV, or ``None``.'''
        image = prepare(image)
        padded, scale, pad = letterbox(image, self.model.size)
        output = self.model.forward(padded)[0]
        xyxy, conf, cls = decode(output, self.confidence, self.iou,
                                 scale, pad, image.shape[:2])
        if len(conf) == 0:
            return None
        return self._features(xyxy, conf, cls, self._labels(cls, output))

    def _labels(self, cls: np.ndarray, output: np.ndarray) -> list[str]:
        '''Return the names of the classes *cls*.'''
        names = self.names
        if names is None and output.shape[-2] - 4 == len(COCO_NAMES):
            names = COCO_NAMES
        return [names[c] if names is not None and c < len(names) else str(c)
                for c in cls]

    @staticmethod
    def _features(xyxy, conf, cls, labels):
        '''Return the detections as a table.'''
        return pd.DataFrame({
            'x1': xyxy[:, 0],
            'y1': xyxy[:, 1],
            'x2': xyxy[:, 2],
            'y2': xyxy[:, 3],
            'confidence': conf,
            'class': cls,
            'label': labels,
        })


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
    backend, imgsz, names :
        What runs the network, and the size and class names of an ONNX
        model.  See :class:`_YoloWorker`.  The default runs a ``.onnx``
        file with OpenCV and anything else with ``ultralytics``.
    '''

    def __init__(self,
                 parent: QtWidgets.QWidget | None = None,
                 model_name: str = 'yolo11n.pt',
                 confidence: float = 0.25,
                 backend: str = 'auto',
                 imgsz: int = 640,
                 names: Sequence[str] | None = None) -> None:
        worker = _YoloWorker(model_name=model_name, confidence=confidence,
                             backend=backend, imgsz=imgsz, names=names)
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
