from QVideo.lib import QCameraTree
from QVideo.cameras.Noise import QNoiseSource


class QNoiseTree(QCameraTree):

    def __init__(self, *args,
                 cameraID: int = 0,
                 **kwargs) -> None:
        camera = QNoiseSource()
        controls = None
        super().__init__(camera, controls, *args, **kwargs)


if __name__ == '__main__':
    QNoiseTree.example()
