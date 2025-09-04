from QCamcorder import QCamcorder
from pyqtgraph.Qt.QtCore import (pyqtSignal, pyqtSlot,
                                 pyqtProperty, QObject)
import pyqtgraph as pg
import numpy as np


class ROIFilter(QObject):

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.fps = parent.source.fps
        self.roi = parent.roi
        self.image = parent.screen.image

    @pyqtSlot(np.ndarray)
    def crop(self, frame: np.ndarray) -> None:
        crop = self.roi.getArrayRegion(frame, self.image).astype(np.uint8)
        self.newFrame.emit(crop)


class ROIdemo(QCamcorder):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.filter = ROIFilter(self)
        self.dvr.source = self.filter

    def _setupUi(self) -> None:
        super()._setupUi()
        self.roi = pg.RectROI([100, 100], [400, 400],
                              snapSize=8,
                              scaleSnap=True,
                              sideScalers=True,
                              rotatable=False)
        self.screen.view.addItem(self.roi)

    def connectSignals(self) -> None:
        super().connectSignals()
        self.dvr.recording.connect(self.recording)

    @pyqtSlot(bool)
    def recording(self, active: bool) -> None:
        if active:
            self.source.newFrame.connect(self.filter.crop)
        else:
            self.source.newFrame.disconnect(self.filter.crop)


def main() -> None:
    from QVideo.cameras.choose_camera import choose_camera_widget

    CameraWidget = choose_camera_widget()

    app = pg.mkQApp()
    cameraWidget = CameraWidget().start()
    widget = ROIdemo(cameraWidget=cameraWidget)
    widget.show()
    app.exec()


if __name__ == '__main__':
    main()
