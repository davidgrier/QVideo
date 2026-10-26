#!/usr/bin/env python3
'''Demo: object detection with YOLO, drawn over the video.

Run directly::

    python -m QVideo.demos.yolodemo

See :mod:`QVideo.overlays.yolo` for literature references.
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree, launch
from QVideo.overlays import QYoloWidget


__all__ = ['YoloDemo']


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
        Default: ``'yolo11n.pt'``.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~QVideo.demos.demo.Demo`.
    '''

    def __init__(self,
                 cameraTree: QCameraTree,
                 model_name: str = 'yolo11n.pt',
                 **kwargs) -> None:
        self._modelName = model_name  # _setupUi runs inside super().__init__
        super().__init__(cameraTree, **kwargs)

    def _setupUi(self) -> None:
        super()._setupUi()
        self.yolo = QYoloWidget(self, model_name=self._modelName)
        self.yolo.source = self.cameraTree.source
        self.screen.addOverlay(self.yolo.overlay)
        self._controls.addWidget(self.yolo)


if __name__ == '__main__':  # pragma: no cover
    launch(YoloDemo, 'YOLO Demo')
