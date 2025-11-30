#!/usr/bin/env python3

from QVideo.lib import (QVideoScreen, QCameraTree)
from pyqtgraph.Qt.QtWidgets import (QWidget, QHBoxLayout)


class demo(QWidget):
    '''A demo widget that displays a video feed from a camera
    alongside a camera control tree.

    Parameters
    ----------
    cameraWidget : QCameraTree
        The camera control tree widget to display alongside the video feed.
    kwargs : dict
        Additional keyword arguments to pass to the QWidget constructor.

    Returns
    -------
    demo : QWidget
        The demo widget containing the video feed and camera control tree.

    Notes
    -----
    This widget sets up a horizontal layout containing a video screen
    and a camera control tree. It connects the camera source's newFrame
    signal to update the video screen and adjusts the screen shape
    when the camera source's shape changes.
    '''

    def __init__(self, cameraWidget: QCameraTree, **kwargs) -> None:
        super().__init__(**kwargs)
        self.screen = QVideoScreen(self)
        self.cameraWidget = cameraWidget
        self._setupUi()
        self.screen.source = self.cameraWidget.source

    def _setupUi(self) -> None:
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.cameraWidget)


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
