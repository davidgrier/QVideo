#!/usr/bin/env python3
'''Demo: image filters between the camera and the screen.

Run directly::

    python -m QVideo.demos.filterdemo
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree, QFilterRack, launch


__all__ = ['FilterDemo']


class FilterDemo(Demo):

    '''The camera's frames, filtered before they are displayed.

    Data flow::

        camera -> filter pipeline -> screen

    The recipe is a :class:`~QVideo.lib.QFilterRack.QFilterRack`, a panel of
    filters that owns the worker thread running them.  The screen displays
    the rack's ``pipeline`` instead of the camera, so a slow filter leaves
    the interface responsive.  Each filter can be switched on and off and
    adjusted alongside the live feed.  See
    :mod:`~QVideo.demos.filterrackdemo` for a rack that can be edited while
    the program runs.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    filters : list[str]
        Display names of the filters to add to the rack, for example
        ``'Smoothing'`` or ``'Canny'`` (see
        :meth:`~QVideo.lib.QFilterRack.QFilterRack.availableFilters`).
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~QVideo.demos.demo.Demo`.
    '''

    def __init__(self,
                 cameraTree: QCameraTree,
                 filters: list[str],
                 **kwargs) -> None:
        self._filters = filters  # _setupUi runs inside super().__init__
        super().__init__(cameraTree, **kwargs)

    def _setupUi(self) -> None:
        super()._setupUi()
        self.rack = QFilterRack(self, editable=False,
                                source=self.cameraTree.source)
        for name in self._filters:
            self.rack.addByName(name)
        self.screen.source = self.rack.pipeline
        self._controls.addWidget(self.rack)


if __name__ == '__main__':  # pragma: no cover
    launch(FilterDemo, 'Filter Demo',
           filters=['Color Channel', 'Smoothing', 'Sample and Hold',
                    'Threshold', 'Blob', 'Canny'])
