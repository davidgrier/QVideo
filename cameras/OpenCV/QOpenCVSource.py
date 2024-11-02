from QVideo.cameras.OpenCV import QOpenCVCamera
from QVideo.lib import QVideoSource
from typing import Optional


class QOpenCVSource(QVideoSource):

    def __init__(self, *args,
                 camera: Optional[QOpenCVCamera] = None,
                 **kwargs) -> None:
        camera = camera or QOpenCVCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':
    QOpenCVSource.example()
