#!/usr/bin/env python3
'''Demo combining a live video feed, camera controls, and an image-filter bank.

Run directly::

    python -m QVideo.demos.filterdemo
'''

from QVideo.lib import QVideoScreen, QCameraTree
from pyqtgraph.Qt.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout


__all__ = ['Demo']


class Demo(QWidget):
    '''A demo widget that displays a video feed from a camera
    alongside a camera control tree and filter bank.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    filters : list[str]
        Names of filter classes to register from :mod:`QVideo.filters`.
    **kwargs :
        Additional keyword arguments forwarded to :class:`QWidget`.

    Notes
    -----
    Sets up a horizontal layout containing a video screen on the left
    and a vertical layout on the right for camera controls and filters.
    '''

    def __init__(self,
                 cameraTree: QCameraTree,
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
    '''Launch the filter demo with an interactively chosen camera.'''
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    pg.mkQApp()
    camera = choose_camera().start()
    filters = 'QRGBFilter QBlurFilter QSampleHold QEdgeFilter'.split()
    widget = Demo(camera, filters)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
