#!/usr/bin/env python3
'''Minimal demo: live video screen alongside a camera control tree.

Run directly::

    python -m QVideo.demos.demo
'''

from QVideo.lib import QVideoScreen
from pyqtgraph.Qt.QtWidgets import QWidget, QHBoxLayout


__all__ = ['Demo']


class Demo(QWidget):
    '''A demo widget that displays a video feed from a camera
    alongside a camera control tree.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    **kwargs :
        Additional keyword arguments forwarded to :class:`QWidget`.

    Notes
    -----
    Sets up a horizontal layout containing a video screen on the left
    and a camera control tree on the right.
    '''

    def __init__(self, cameraTree: 'QCameraTree', **kwargs) -> None:
        super().__init__(**kwargs)
        self.screen = QVideoScreen()
        self.cameraTree = cameraTree
        self._setupUi()
        self.screen.source = self.cameraTree.source

    def _setupUi(self) -> None:
        layout = QHBoxLayout(self)
        layout.addWidget(self.screen)
        layout.addWidget(self.cameraTree)


def main() -> None:  # pragma: no cover
    '''Launch the demo with an interactively chosen camera.'''
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    pg.mkQApp()
    camera = choose_camera().start()
    widget = Demo(camera)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
