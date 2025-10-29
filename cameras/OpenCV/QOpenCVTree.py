from QVideo.lib import QCameraTree
from QVideo.cameras.OpenCV import QOpenCVCamera


class QOpenCVTree(QCameraTree):
    '''Threaded camera tree that uses OpenCV to access camera devices.

    Inherits
    --------
    QVideo.lib.QCameraTree

    Parameters
    ----------
    camera : QOpenCVCamera | None
        An instance of QOpenCVCamera. If None, a new instance is created.
    cameraID : int
        ID of the camera device (default is 0).
    '''

    def __init__(self, *args,
                 camera: QCameraTree.Source | None = None,
                 cameraID: int = 0,
                 **kwargs) -> None:
        camera = camera or QOpenCVCamera(*args, cameraID=cameraID, **kwargs)
        controls = None
        super().__init__(camera, controls, *args, **kwargs)


if __name__ == '__main__':
    QOpenCVTree.example()
