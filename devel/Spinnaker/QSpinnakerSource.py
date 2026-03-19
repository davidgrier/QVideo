from QVideo.cameras.Spinnaker import QSpinnakerCamera
from QVideo.lib import QVideoSource


class QSpinnakerSource(QVideoSource):

    def __init__(self, *args,
                 camera: QSpinnakerCamera | None = None,
                 **kwargs) -> None:
        camera = camera or QSpinnakerCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':
    QSpinnakerSource.example()
