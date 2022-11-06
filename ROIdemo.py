from QBasicDVR import QBasicDVR
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, pyqtProperty)
import pyqtgraph as pg
import numpy as np


class ROIDVR(QBasicDVR):

    newFrame = pyqtSignal(np.ndarray)

    def setupUi(self) -> None:
        super().setupUi()
        self.roi = pg.RectROI([100, 100], [400, 400],
                              snapSize=8,
                              scaleSnap=True,
                              sideScalers=True,
                              rotatable=False)
        self.screen.view.addItem(self.roi)

    def connectSignals(self) -> None:
        super().connectSignals()
        self.dvr.source = self
        self.dvr.recording.connect(self.recording)

    @pyqtSlot(bool)
    def recording(self, active: bool) -> None:
        if active:
            self.camera.newFrame.connect(self.cropFrame)
        else:
            self.camera.newFrame.disconnect(self.cropFrame)

    @pyqtSlot(np.ndarray)
    def cropFrame(self, frame: np.ndarray) -> None:
        x0, y0 = map(int, self.roi.pos())
        w, h = map(int, self.roi.size())
        crop = frame[y0:y0+h, x0:x0+w, ...]
        self.newFrame.emit(crop)

    @pyqtProperty(float)
    def fps(self) -> float:
        return self.camera.fps


def example():
    from QVideo.cameras.OpenCV import QOpenCVTree

    pg.mkQApp('DVR')
    widget = ROIDVR(cameraWidget=QOpenCVTree())
    widget.show()
    pg.exec()


if __name__ == '__main__':
    example()
