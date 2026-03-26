#!/usr/bin/env python3
'''Demo combining a live video feed, camera controls, and an image-filter bank.

Run directly::

    python -m QVideo.demos.filterdemo
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree


__all__ = ['FilterDemo']


class FilterDemo(Demo):
    '''Extends :class:`~QVideo.demos.demo.Demo` with an image-filter bank.

    Adds a :class:`~QVideo.lib.QFilterBank.QFilterBank` panel below the
    camera control tree so that image-processing filters can be toggled
    and adjusted alongside the live feed.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    filters : list[str]
        Names of filter classes to register from :mod:`QVideo.filters`.
    **kwargs :
        Additional keyword arguments forwarded to :class:`~QVideo.demos.demo.Demo`.
    '''

    def __init__(self,
                 cameraTree: QCameraTree,
                 filters: list[str],
                 **kwargs) -> None:
        super().__init__(cameraTree, **kwargs)
        self.addFilters(filters)

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
    filters = 'QYOLOFilter QRGBFilter QSampleHold QBlurFilter QEdgeFilter'.split()
    widget = FilterDemo(camera, filters)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
