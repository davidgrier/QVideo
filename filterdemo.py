#!/usr/bin/env python3

from QVideo.lib import (QVideoScreen, QCameraTree)
from QVideo.filters.RGBFilter import QRGBFilter
from pyqtgraph.Qt.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout)


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
    on the left and a vertical layout on the right for camera controls
    and filters. It initializes the video screen with the source from
    the provided camera widget and adds an RGB filter to the control layout.
    '''

    def __init__(self, cameraWidget: QCameraTree, **kwargs) -> None:
        super().__init__(**kwargs)
        self.screen = QVideoScreen(self)
        self.cameraWidget = cameraWidget
        self._setupUi()
        self.screen.source = self.cameraWidget.source
        self.addFilter()

    def _setupUi(self) -> None:
        layout = QHBoxLayout(self)
        layout.addWidget(self.screen)
        controls = QWidget(self)
        layout.addWidget(controls)
        self.controlLayout = QVBoxLayout(controls)
        self.controlLayout.addWidget(self.cameraWidget)

    def addFilter(self) -> None:
        rgbFilter = QRGBFilter(self)
        self.controlLayout.addWidget(rgbFilter)
        self.screen.filter.register(rgbFilter.filter)


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
