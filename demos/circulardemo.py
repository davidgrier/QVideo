#!/usr/bin/env python3
'''Demo combining a live video feed, camera controls, and a circular-buffer DVR.

Run directly::

    python -m QVideo.demos.circulardemo
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree, launch
from QVideo.dvr import QCircularDVRWidget


__all__ = ['CircularDemo']


class CircularDemo(Demo):

    '''Extends :class:`~QVideo.demos.demo.Demo` with a circular-buffer DVR.

    Adds a :class:`~QVideo.dvr.QCircularDVRWidget.QCircularDVRWidget`
    below the camera control tree.  The buffer accumulates continuously;
    clicking **Save** writes the last N seconds to disk without any
    prior *record* action.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~QVideo.demos.demo.Demo`.
    '''

    def __init__(self, cameraTree: QCameraTree, **kwargs) -> None:
        super().__init__(cameraTree, **kwargs)
        self.dvr = QCircularDVRWidget(self.screen.source)
        self._controls.addWidget(self.dvr)


if __name__ == '__main__':  # pragma: no cover
    launch(CircularDemo, 'Circular Buffer Demo')
