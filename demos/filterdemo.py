#!/usr/bin/env python3
'''Demo combining a live video feed, camera controls, and image filters.

Run directly::

    python -m QVideo.demos.filterdemo
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree, QFilterRack, launch


__all__ = ['FilterDemo']


class FilterDemo(Demo):
    '''Extends :class:`~QVideo.demos.demo.Demo` with image filters.

    The filters appear in a fixed
    :class:`~QVideo.lib.QFilterRack.QFilterRack` below the camera control
    tree, where each one can be switched on and off and adjusted alongside
    the live feed.  The rack runs them on a worker thread between the
    camera and the screen, so even a slow filter leaves the interface
    responsive.  See :mod:`~QVideo.demos.filterrackdemo` for a rack
    that can be edited while the program runs.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    filters : list[str]
        Display names of the filters to add to the rack, for example
        ``'Smoothing'`` or ``'Canny'`` (see
        :meth:`~QVideo.lib.QFilterRack.QFilterRack.availableFilters`).
    **kwargs :
        Additional keyword arguments forwarded to :class:`~QVideo.demos.demo.Demo`.
    '''

    def __init__(self,
                 cameraTree: QCameraTree,
                 filters: list[str],
                 **kwargs) -> None:
        super().__init__(cameraTree, **kwargs)
        self.rack = QFilterRack(self, editable=False)
        self.rack.source = self.cameraTree.source
        self.screen.source = self.rack.pipeline
        self._controls.addWidget(self.rack)
        for name in filters:
            self.rack.addByName(name)


if __name__ == '__main__':  # pragma: no cover
    launch(FilterDemo, 'Filter Demo',
           filters=['Color Channel', 'Smoothing', 'Sample and Hold',
                    'Threshold', 'Blob', 'Canny'])
