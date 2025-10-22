from QVideo.lib import (QVideoScreen, QCameraTree)
from pyqtgraph.Qt.QtWidgets import (QWidget, QHBoxLayout)


class demo(QWidget):

    def __init__(self, cameraWidget: QCameraTree, **kwargs) -> None:
        super().__init__(**kwargs)
        self.screen = QVideoScreen(self)
        self.cameraWidget = cameraWidget
        self.screen.setSource(self.cameraWidget.source)
        self._setupUi()

    def _setupUi(self) -> None:
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.cameraWidget)
        self._updateShape()

    def _connectSignals(self) -> None:
        source = self.cameraWidget.source
        source.newFrame.connect(self.screen.setImage)
        source.shapeChanged.connect(self._updateShape)

    def _updateShape(self) -> None:
        source = self.cameraWidget.source
        self.screen.updateShape(source.shape)


def main() -> None:
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    app = pg.mkQApp()
    camera = choose_camera().start()
    widget = demo(camera)
    widget.show()
    pg.exec()


if __name__ == '__main__':
    main()
