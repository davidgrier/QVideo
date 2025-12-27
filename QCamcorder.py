#!/usr/bin/env python3

from pyqtgraph.Qt.QtWidgets import QWidget
from pyqtgraph.Qt.QtCore import pyqtSlot
from pyqtgraph.Qt import uic
from QVideo.lib import QCameraTree
from pathlib import Path


class QCamcorder(QWidget):
    '''A widget that combines a video screen with camera controls
    and DVR functionality.

    Parameters
    ----------
    cameraWidget : QCameraTree
        The camera control widget to display alongside the video feed.
    args : tuple
        Additional parameters to pass to the QWidget constructor.
    kwargs : dict
        Additional keyword arguments to pass to the QWidget constructor.

    Returns
    -------
    QCamcorder : QWidget
        The camcorder widget containing the video feed, camera controls,
        and DVR functionality.

    Notes
    -----
    This widget loads its UI from a .ui file and sets up the video screen,
    camera controls, and DVR functionality. It connects the camera source's
    newFrame signal to update the video screen and adjusts the screen shape
    when the camera source's shape changes. It also manages playback state
    for the DVR.
    '''

    UIFILE = 'QCamcorder.ui'

    def __init__(self,
                 cameraWidget: QCameraTree,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraWidget = cameraWidget
        self.source = self.cameraWidget.source
        self._setupUi()
        self._connectSignals()
        self.screen.source = self.source
        self.dvr.source = self.source

    def _setupUi(self) -> None:
        uifile = str(Path(__file__).parent / self.UIFILE)
        uic.loadUi(uifile, self)
        self.controls.layout().addWidget(self.cameraWidget)

    def _connectSignals(self) -> None:
        self.dvr.playing.connect(self.dvrPlayback)

    @pyqtSlot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        if playback:
            self.source.newFrame.disconnect(self.screen.setImage)
            self.dvr.newFrame.connect(self.screen.setImage)
        else:
            self.source.newFrame.connect(self.screen.setImage)
        self.cameraWidget.setDisabled(playback)


def main() -> None:
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    app = pg.mkQApp()
    camera = choose_camera()
    widget = QCamcorder(camera.start())
    widget.show()
    pg.exec()


if __name__ == '__main__':
    main()
