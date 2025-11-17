#!/usr/bin/env python3

from QVideo.QCamcorder import QCamcorder
from pyqtgraph.Qt.QtCore import (pyqtSignal, pyqtSlot)
from pyqtgraph.Qt.QtWidgets import QWidget
import pyqtgraph as pg
import numpy as np
from pathlib import Path


class ROIFilter(pg.RectROI):
    '''A rectangular region of interest (ROI) filter that crops frames
    to the defined ROI area.

    Parameters
    ----------
    fps : float
        Frame rate of the video source [frames per second].
        This property is required for QVideoWriter compatibility.
    *args : list
        Additional positional arguments to pass to the Rect
        ROI constructor.
    **kwargs : dict
        Additional keyword arguments to pass to the Rect
        ROI constructor.

    Signals
    -------
    newFrame(np.ndarray)
        Emitted when a new cropped frame is available.

    Slots
    -----
    crop(frame: np.ndarray) -> None
        Crops the input frame to the defined ROI area and emits
        the cropped frame via the newFrame signal.

    Returns
    -------
    ROIFilter : pg.RectROI
        The ROI filter that emits cropped frames.
    '''

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, fps: float, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fps = fps

    @pyqtSlot(np.ndarray)
    def crop(self, frame: np.ndarray) -> None:
        x, y = self.pos()
        w, h = self.size()
        crop = frame[int(y):int(y + h), int(x):int(x + w)]
        self.newFrame.emit(crop)


class ROIdemo(QCamcorder):
    '''A demo widget that displays a video feed with an ROI filter
    for cropping the video frames.

    Parameters
    ----------
    cameraWidget : QCameraTree
        The camera control tree widget to display alongside the video feed.
    kwargs : dict
        Additional keyword arguments to pass to the QWidget constructor.

    Returns
    -------
    ROIdemo : QCamcorder
        The demo widget containing the video feed with ROI cropping
        functionality.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.roi = ROIFilter(self.source.fps,
                             [100, 100], [400, 400],
                             snapSize=8,
                             scaleSnap=True,
                             sideScalers=True,
                             movable=True,
                             invertible=False,
                             rotatable=False,
                             removable=False)
        self.screen.view.addItem(self.roi)
        self.dvr.filename = str(Path.home() / 'roidemo.avi')

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self.dvr.source = self.roi
        self.dvr.recording.connect(self.recording)

    @pyqtSlot(bool)
    def recording(self, recording: bool) -> None:
        if recording:
            self.roi.movable = False
            self.source.newFrame.connect(self.roi.crop)
        else:
            self.roi.movable = True
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
