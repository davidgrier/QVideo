#!/usr/bin/env python3
'''Minimal demo: live video screen alongside a camera control tree.

This is the starting point for every recipe in this package.
Run it directly::

    python -m QVideo.demos.demo
'''

from qtpy import QtWidgets
from QVideo.lib import QVideoScreen, QCameraTree, launch


__all__ = ['Demo']


class Demo(QtWidgets.QWidget):
    '''Live video beside the controls of the camera that makes it.

    Data flow::

        camera -> screen

    A recipe extends this class by one idea.  It overrides :meth:`_setupUi`
    and calls ``super()._setupUi()`` first, which makes the screen and the
    panel of controls.  It then builds its widget, connects it to the
    camera's source (``self.cameraTree.source``) or to :attr:`screen`, and
    adds it to the panel, ``self._controls``.  See
    :class:`~QVideo.demos.histogramdemo.HistogramDemo` for the smallest
    example.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    **kwargs :
        Additional keyword arguments forwarded to :class:`QWidget`.
    '''

    def __init__(self, cameraTree: QCameraTree, **kwargs) -> None:
        super().__init__(**kwargs)
        self.screen = QVideoScreen()
        self.cameraTree = cameraTree
        self.screen.source = self.cameraTree.source
        self._setupUi()

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
