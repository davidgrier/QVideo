#!/usr/bin/env python3

from QVideo.lib import QVideoScreen
from pyqtgraph.Qt.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout


class demo(QWidget):
    '''A demo widget that displays a video feed from a camera
    alongside a camera control tree and filter bank.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    filters : list[str]
        List of the names of filters to include in filter bank.
    kwargs : dict
        Additional keyword arguments to pass to the QWidget constructor.

    Notes
    -----
    Sets up a horizontal layout containing a video screen on the left
    and a vertical layout on the right for camera controls and filters.
    '''

    def __init__(self,
                 cameraTree: 'QCameraTree',
                 filters: list[str],
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.screen = QVideoScreen()
        self.cameraTree = cameraTree
        self._setupUi()
        self.screen.source = self.cameraTree.source
        self.addFilters(filters)

    def _setupUi(self) -> None:
        layout = QHBoxLayout(self)
        layout.addWidget(self.screen)
        self._controls = QVBoxLayout()
        layout.addLayout(self._controls)
        self._controls.addWidget(self.cameraTree)

    def addFilters(self, filters: list[str]) -> None:
        '''Register filters by name and show the filter bank.

        Parameters
        ----------
        filters : list[str]
            Names of filter classes to register from :mod:`QVideo.filters`.
        '''
        for name in filters:
            self.screen.filter.registerByName(name)
        self._controls.addWidget(self.screen.filter)
        self.screen.filter.setVisible(True)


def main() -> None:  # pragma: no cover
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    pg.mkQApp()
    camera = choose_camera().start()
    filters = 'QRGBFilter QBlurFilter QSampleHold QEdgeFilter'.split()
    widget = demo(camera, filters)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
