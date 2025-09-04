from QVideo.cameras.Flir import QFlirCamera
from QVideo.lib import QVideoSource


class QFlirSource(QVideoSource):

    def __init__(self, *args,
                 camera: QFlirCamera | None = None,
                 **kwargs) -> None:
        camera = camera or FlirCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':
    QFlirSource.example()
