from QVideo.lib import QCameraTree
from QVideo.cameras.Noise import QNoiseSource


class QNoiseTree(QCameraTree):

    def __init__(self, *args, **kwargs) -> None:
        camera = QNoiseSource()
        controls = None
        super().__init__(camera, controls, *args, **kwargs)


def example() -> None:
    from pyqtgraph.Qt.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    widget = QNoiseTree()
    widget.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    example()
