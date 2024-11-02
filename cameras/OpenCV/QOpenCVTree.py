from QVideo.lib import QCameraTree
from QVideo.cameras.OpenCV import QOpenCVCamera
from typing import Optional


class QOpenCVTree(QCameraTree):

    def __init__(self, *args,
                 camera: Optional[QCameraTree.Source] = None,
                 **kwargs) -> None:
        camera = camera or QOpenCVCamera(*args, **kwargs)
        controls = None
        super().__init__(camera, controls, *args, **kwargs)


if __name__ == '__main__':
    QOpenCVTree.example()
