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
    parent : QWidget
        The parent widget that contains the source and screen attributes.
    *args : list
        Additional positional arguments to pass to the Rect
        ROI constructor.
    **kwargs : dict
        Additional keyword arguments to pass to the Rect
        ROI constructor.

    Returns
    -------
    ROIFilter : pg.RectROI
        The ROI filter that emits cropped frames.
    '''

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, parent: QWidget, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fps = parent.source.fps
        self.image = parent.screen.image

    @pyqtSlot(np.ndarray)
    def crop(self, frame: np.ndarray) -> None:
        '''Crops the input frame to the defined ROI area and emits
        the cropped frame.

        Parameters
        ----------
        frame : np.ndarray
            The input video frame to be cropped.
        '''
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
