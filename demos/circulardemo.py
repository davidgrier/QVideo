#!/usr/bin/env python3
'''Demo: a circular-buffer DVR beside the video.

Run directly::

    python -m QVideo.demos.circulardemo
'''

from QVideo.demos.demo import Demo
from QVideo.lib import launch
from QVideo.dvr import QCircularDVRWidget


__all__ = ['CircularDemo']


class CircularDemo(Demo):

    '''A recorder that always holds the last few seconds of video.

    Data flow::

        camera -> screen
           '----> circular buffer -> file, when you click Save

    The recipe is one widget that listens to the camera, not to the screen,
    so it keeps every frame at the camera's full rate:
    :class:`~QVideo.dvr.QCircularDVRWidget.QCircularDVRWidget`.  The buffer
    fills continuously, and **Save** writes the last N seconds to disk
    without a prior *record*.  See :class:`~QVideo.demos.demo.Demo` for the
    parameters.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.dvr = QCircularDVRWidget(self.cameraTree.source)
        self._controls.addWidget(self.dvr)


if __name__ == '__main__':  # pragma: no cover
    launch(CircularDemo, 'Circular Buffer Demo')
