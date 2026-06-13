#!/usr/bin/env python3
'''Demo combining a live video feed, camera controls, and illumination-uniformity plots.

Run directly::

    python -m QVideo.demos.uniformitydemo
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree, QUniformityWidget


__all__ = ['UniformityDemo']


class UniformityDemo(Demo):

    '''Extends :class:`~QVideo.demos.demo.Demo` with illumination-uniformity plots.

    Adds a :class:`~QVideo.lib.QUniformityWidget.QUniformityWidget` below
    the camera control tree.  The widget shows mean intensity as a function
    of x (averaged over y) and as a function of y (averaged over x),
    updating on every displayed frame.  Flat traces indicate uniform
    illumination; any slope, dip, or peak localises non-uniformity
    spatially.

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
        self.uniformity = QUniformityWidget(self.screen)
        self._controls.addWidget(self.uniformity)


def main() -> None:  # pragma: no cover
    '''Launch the uniformity demo with an interactively chosen camera.'''
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    from qtpy import QtGui, QtWidgets
    app = pg.mkQApp('Uniformity Demo')
    camera = choose_camera().start()
    widget = UniformityDemo(camera)
    QtWidgets.QShortcut(
        QtGui.QKeySequence('Ctrl+Q'), widget
    ).activated.connect(app.quit)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
