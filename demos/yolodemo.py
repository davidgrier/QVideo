#!/usr/bin/env python3
'''Demo: object detection with YOLO, drawn over the video.

Run directly::

    python -m QVideo.demos.yolodemo
    python -m QVideo.demos.yolodemo --model yolo11n.onnx

A model whose name ends in ``.onnx`` runs with OpenCV, with no ``torch``;
any other runs with ``ultralytics``.  ``--imgsz`` and ``--names`` describe an
ONNX model, and ``--backend`` overrides the choice by extension.  See
:mod:`QVideo.overlays.yolo` for how to prepare the file and for literature
references.
'''

from collections.abc import Sequence

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree, launch
from QVideo.lib._launch import argumentParser
from QVideo.overlays import QYoloWidget


__all__ = ['YoloDemo', 'options']


class YoloDemo(Demo):

    '''Detected objects marked on the live video.

    Data flow::

        camera -> screen
           '----> YOLO (worker thread) -> boxes on the screen

    The recipe is the same as for
    :class:`~QVideo.demos.trackpydemo.TrackpyDemo` with another detector:
    :class:`~QVideo.overlays.yolo.QYoloWidget` holds the controls, and its
    ``overlay`` draws the bounding boxes.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    model_name : str
        YOLO model weights file passed to
        :class:`~QVideo.overlays.yolo.QYoloWidget`.
        Default: ``'yolo11n.pt'``.  A ``.onnx`` file runs with OpenCV.
    backend : {'auto', 'ultralytics', 'opencv'}
        What runs the network.  ``'auto'`` chooses by the extension of
        *model_name*.
    imgsz : int
        Side of the input of an ONNX model [pixels].  Default: ``640``.
    names : sequence of str or None
        Names of the classes of an ONNX model.  The default is the 80
        names of COCO if the network has 80 classes.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~QVideo.demos.demo.Demo`.
    '''

    def __init__(self,
                 cameraTree: QCameraTree,
                 model_name: str = 'yolo11n.pt',
                 backend: str = 'auto',
                 imgsz: int = 640,
                 names: Sequence[str] | None = None,
                 **kwargs) -> None:
        # _setupUi runs inside super().__init__
        self._model = dict(model_name=model_name, backend=backend,
                           imgsz=imgsz, names=names)
        super().__init__(cameraTree, **kwargs)

    def _setupUi(self) -> None:
        super()._setupUi()
        self.yolo = QYoloWidget(self, **self._model)
        self.yolo.source = self.cameraTree.source
        self.screen.addOverlay(self.yolo.overlay)
        self._controls.addWidget(self.yolo)


def options(argv: Sequence[str] | None = None) -> dict:
    """Return the keyword arguments of :class:`YoloDemo` from *argv*.

    The parser has the camera flags too, so that ``--help`` lists everything;
    the camera is chosen from the same command line by ``launch``.
    """
    parser = argumentParser(YoloDemo, examples=(
        ('--model yolo11n.onnx', 'an ONNX model, run by OpenCV'),
        ('--model m.onnx --names a,b --imgsz 320', 'your own classes')))
    model = parser.add_argument_group('model')
    model.add_argument('--model', default='yolo11n.pt', metavar='FILE',
                       help='model file: .onnx runs with OpenCV, anything '
                       'else with ultralytics (default: yolo11n.pt)')
    model.add_argument('--backend', default='auto',
                       choices=('auto', 'ultralytics', 'opencv'),
                       help='what runs the network (default: by the '
                       'extension of the model)')
    model.add_argument('--imgsz', type=int, default=640, metavar='PIXELS',
                       help='input size of an ONNX model (default: 640)')
    model.add_argument('--names', metavar='A,B,...',
                       help='comma-separated class names of an ONNX model '
                       '(default: COCO if the network has 80 classes)')
    args, _ = parser.parse_known_args(argv)
    return dict(model_name=args.model, backend=args.backend,
                imgsz=args.imgsz,
                names=args.names.split(',') if args.names else None)


if __name__ == '__main__':  # pragma: no cover
    launch(YoloDemo, 'YOLO Demo', **options())
