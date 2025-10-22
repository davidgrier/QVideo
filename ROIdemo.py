from QVideo.QCamcorder import QCamcorder
from pyqtgraph.Qt.QtCore import (pyqtSignal, pyqtSlot)
import pyqtgraph as pg
import numpy as np
from pathlib import Path


class ROIFilter(pg.RectROI):

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, parent, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fps = parent.source.fps
        self.image = parent.screen.image

    @pyqtSlot(np.ndarray)
    def crop(self, frame: np.ndarray) -> None:
        crop = self.getArrayRegion(frame, self.image).astype(np.uint8)
        self.newFrame.emit(crop)


class ROIdemo(QCamcorder):

    def _setupUi(self) -> None:
        super()._setupUi()
        self.roi = ROIFilter(self, [100, 100], [400, 400],
                             snapSize=8,
                             scaleSnap=True,
                             sideScalers=True,
                             rotatable=False)
        self.screen.view.addItem(self.roi)
        self.dvr.filename = str(Path.home() / 'crop.avi')

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self.dvr.source = self.roi
        self.dvr.recording.connect(self.recording)

    @pyqtSlot(bool)
    def recording(self, recording: bool) -> None:
        if recording:
            self.source.newFrame.connect(self.roi.crop)
        else:
            self.source.newFrame.disconnect(self.roi.crop)


def main() -> None:
    from QVideo.lib import choose_camera

    app = pg.mkQApp()
    camera = choose_camera().start()
    widget = ROIdemo(camera)
    widget.show()
    app.exec()


if __name__ == '__main__':
    main()
