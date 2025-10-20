from QVideo.lib import QCameraTree
from QVideo.cameras.OpenCV import QOpenCVCamera


class QOpenCVTree(QCameraTree):

    def __init__(self, *args,
                 camera: QCameraTree.Source | None = None,
                 cameraID: int = 0,
                 **kwargs) -> None:
        camera = camera or QOpenCVCamera(*args, cameraID=cameraID, **kwargs)
        controls = None
        super().__init__(camera, controls, *args, **kwargs)


if __name__ == '__main__':
    QOpenCVTree.example()
