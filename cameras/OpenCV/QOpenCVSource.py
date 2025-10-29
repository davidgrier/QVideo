from QVideo.cameras.OpenCV import QOpenCVCamera
from QVideo.lib import QVideoSource


class QOpenCVSource(QVideoSource):
    '''Threaded video source that uses OpenCV to access a camera device.

    Inherits
    --------
    QVideo.lib.QVideoSource

    Parameters
    ----------
    camera : QOpenCVCamera | None
        An instance of QOpenCVCamera. If None, a new instance is created.
    Other parameters are passed to QOpenCVCamera if camera is None.
    '''

    def __init__(self, *args,
                 camera: QOpenCVCamera | None = None,
                 **kwargs) -> None:
        camera = camera or QOpenCVCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':
    QOpenCVSource.example()
