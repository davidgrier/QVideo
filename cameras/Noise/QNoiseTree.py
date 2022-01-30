from QVideo.lib import QCameraTree
from QVideo.cameras.Noise import QNoiseSource


class QNoiseTree(QCameraTree):

    def __init__(self, *args, camera=None, **kwargs):
        camera = camera or QNoiseSource()
        controls = QCameraTree.controls
        super().__init__(camera, controls, *args, **kwargs)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    widget = QNoiseTree()
    widget.show()

    sys.exit(app.exec())
