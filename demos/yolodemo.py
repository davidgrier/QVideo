#!/usr/bin/env python3
'''Demo combining a live video feed, camera controls, and a YOLO overlay.

Run directly::

    python -m QVideo.demos.yolodemo

See :mod:`QVideo.overlays.yolo` for literature references.
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree
from QVideo.overlays import QYoloWidget


__all__ = ['YoloDemo']


class YoloDemo(Demo):
    '''Extends :class:`~QVideo.demos.demo.Demo` with a YOLO overlay.

    Adds a :class:`~QVideo.overlays.yolo.QYoloWidget` control panel
    below the camera control tree.  Detected object bounding boxes are
    rendered in real time as a rectangle overlay on the video screen.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    model_name : str
        YOLO model weights file passed to :class:`~QVideo.overlays.yolo.QYoloWidget`.
        Default: ``'yolo11n.pt'``.
    **kwargs :
        Additional keyword arguments forwarded to :class:`~QVideo.demos.demo.Demo`.
    '''

    def __init__(self,
                 cameraTree: QCameraTree,
                 model_name: str = 'yolo11n.pt',
                 **kwargs) -> None:
        super().__init__(cameraTree, **kwargs)
        self.yolo = QYoloWidget(self, model_name=model_name)
        self.yolo.source = self.screen.source
        self.screen.addOverlay(self.yolo.overlay)
        self._controls.addWidget(self.yolo)


def main() -> None:  # pragma: no cover
    '''Launch the YOLO demo with an interactively chosen camera.'''
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    pg.mkQApp()
    camera = choose_camera().start()
    widget = YoloDemo(camera)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
