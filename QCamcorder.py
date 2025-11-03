from pyqtgraph.Qt.QtWidgets import QWidget
from pyqtgraph.Qt import uic
from pyqtgraph.Qt.QtCore import pyqtSlot
from pathlib import Path


class QCamcorder(QWidget):
    '''A widget that combines a video screen with camera controls
    and DVR functionality.

    Parameters
    ----------
    cameraWidget : QCameraTree
        The camera control tree widget to display alongside the video feed.
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

    def __init__(self, cameraWidget, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cameraWidget = cameraWidget
        self.source = self.cameraWidget.source
        self._setupUi()
        self._connectSignals()

    def _setupUi(self) -> None:
        uifile = str(Path(__file__).parent / self.UIFILE)
        uic.loadUi(uifile, self)
        self.controls.layout().addWidget(self.cameraWidget)
        self.updateShape()

    def _connectSignals(self) -> None:
        self.source.newFrame.connect(self.screen.setImage)
        self.source.shapeChanged.connect(self.updateShape)
        self.dvr.source = self.source
        self.dvr.playing.connect(self.dvrPlayback)

    def updateShape(self) -> None:
        self.screen.updateShape(self.source.shape)

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
