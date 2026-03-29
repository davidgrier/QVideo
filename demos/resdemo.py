#!/usr/bin/env python3
'''Demo: live video with a resolution/fps control bar.

A :class:`QResolutionControl` strip sits above the video screen so that
width, height, and frame rate can be changed at runtime without stopping
the application.  After each successful apply the camera-control tree
reflects the new hardware-actual values.

Run directly::

    python -m QVideo.demos.resdemo [-b|-c|-f|-i|-m|-p|-r|-v] [cameraID]
'''

from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.Qt.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from QVideo.lib import QCameraTree, QVideoScreen, QResolutionControl


__all__ = ['ResolutionDemo']


class ResolutionDemo(QWidget):
    '''Live video screen with an inline resolution/fps control bar.

    Lays out a :class:`~QVideo.lib.QResolutionControl.QResolutionControl`
    strip at the top of the window, a
    :class:`~QVideo.lib.QVideoScreen.QVideoScreen` on the left, and a
    :class:`~QVideo.lib.QCameraTree.QCameraTree` on the right.

    Pressing **Apply** in the control strip stops the camera thread,
    writes the requested resolution and frame rate, restarts, and then
    updates the camera tree to reflect the hardware-actual values.

    Parameters
    ----------
    cameraTree : QCameraTree
        Camera control tree to embed on the right side.
    resolutions : list[tuple[int, int]] or None
        Optional list of ``(width, height)`` pairs for the resolution
        dropdown.  ``None`` (default) omits the dropdown.
    **kwargs :
        Forwarded to :class:`~pyqtgraph.Qt.QtWidgets.QWidget`.
    '''

    def __init__(self,
                 cameraTree: QCameraTree,
                 resolutions: list[tuple[int, int]] | None = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.cameraTree = cameraTree
        self.screen = QVideoScreen()
        self.resCtrl = QResolutionControl(cameraTree.source,
                                          resolutions=resolutions)
        self._setupUi()
        self.screen.source = cameraTree.source
        self.resCtrl.changed.connect(self._onResolutionChanged)

    def _setupUi(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        outer.addWidget(self.resCtrl)

        row = QHBoxLayout()
        row.addWidget(self.screen)
        row.addWidget(self.cameraTree)
        row.setStretch(0, 1)   # screen takes all surplus horizontal space
        row.setStretch(1, 0)   # tree stays at its natural width
        outer.addLayout(row)

        outer.setStretch(0, 0)   # control bar: fixed height
        outer.setStretch(1, 1)   # video row: fills remaining space

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop the camera source when the window is closed.'''
        self.cameraTree.stop()
        super().closeEvent(event)

    @QtCore.pyqtSlot(int, int, object)
    def _onResolutionChanged(self, width: int, height: int, fps: object) -> None:
        '''Sync the camera tree after a successful resolution change.

        :meth:`~QVideo.lib.QCameraTree.QCameraTree.set` updates the
        named parameter and triggers :meth:`~QVideo.lib.QCameraTree.QCameraTree._sync`,
        which reads back *all* current camera settings, so a single call
        is enough to refresh the whole tree.
        '''
        self.cameraTree.set('width', width)


def main() -> None:  # pragma: no cover
    '''Launch the resolution demo with an interactively chosen camera.'''
    import pyqtgraph as pg
    from QVideo.lib import choose_camera
    from QVideo.lib.resolutions import COMMON_RESOLUTIONS

    pg.mkQApp()
    camera = choose_camera().start()
    resolutions = COMMON_RESOLUTIONS
    widget = ResolutionDemo(camera, resolutions=resolutions)
    widget.setWindowTitle('Resolution Control Demo')
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
