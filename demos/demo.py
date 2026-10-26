#!/usr/bin/env python3
'''Minimal demo: live video screen alongside a camera control tree.

Run directly::

    python -m QVideo.demos.demo
'''

from qtpy import QtWidgets
from QVideo.lib import QVideoScreen, QCameraTree, launch


__all__ = ['Demo']


class Demo(QtWidgets.QWidget):
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

    def __init__(self, cameraTree: QCameraTree, **kwargs) -> None:
        super().__init__(**kwargs)
        self.screen = QVideoScreen()
        self.cameraTree = cameraTree
        self._setupUi()
        self.screen.source = self.cameraTree.source

    def _setupUi(self) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)
        layout.addWidget(self.screen)
        self._controls = QtWidgets.QVBoxLayout()
        self._controls.setContentsMargins(0, 0, 0, 0)
        self._controls.setSpacing(3)
        layout.addLayout(self._controls)
        layout.setStretch(0, 1)  # screen fills horizontal space
        layout.setStretch(1, 0)  # controls retain natural width
        self._controls.addWidget(self.cameraTree)


if __name__ == '__main__':  # pragma: no cover
    launch(Demo, 'QVideo Demo')
