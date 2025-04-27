from QVideo.cameras.Genicam import QGenicamCamera
from QVideo.lib import QVideoSource


class QGenicamSource(QVideoSource):

    def __init__(self, *args,
                 camera: QGenicamCamera | None = None,
                 **kwargs) -> None:
        camera = camera or QGenicamCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':
    QGenicamSource.example()
