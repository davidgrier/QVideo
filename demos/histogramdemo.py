#!/usr/bin/env python3
'''Demo combining a live video feed, camera controls, and an intensity histogram.

Run directly::

    python -m QVideo.demos.histogramdemo
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree, QHistogramWidget


__all__ = ['HistogramDemo']


class HistogramDemo(Demo):

    '''Extends :class:`~QVideo.demos.demo.Demo` with a live intensity histogram.

    Adds a :class:`~QVideo.lib.QHistogramWidget.QHistogramWidget` below
    the camera control tree.  The histogram updates on every displayed
    frame and the draggable level handles adjust the display range fed
    back to the screen.

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
        self.histogram = QHistogramWidget(self.screen)
        self._controls.addWidget(self.histogram)


def main() -> None:  # pragma: no cover
    '''Launch the histogram demo with an interactively chosen camera.'''
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    pg.mkQApp('Histogram Demo')
    camera = choose_camera().start()
    widget = HistogramDemo(camera)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
