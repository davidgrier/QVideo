#!/usr/bin/env python3
'''Camcorder demo with a draggable ROI for recording a cropped video region.

Run directly::

    python -m QVideo.demos.ROIdemo
'''

from QVideo.QCamcorder import QCamcorder
from pyqtgraph.Qt.QtCore import pyqtSignal, pyqtSlot
import pyqtgraph as pg
import numpy as np
from pathlib import Path


__all__ = ['ROIFilter', 'ROIDemo']


class ROIFilter(pg.RectROI):
    '''Draggable rectangular ROI that crops video frames to its bounds.

    Subclasses :class:`pyqtgraph.RectROI` and adds a :attr:`newFrame`
    signal and :meth:`crop` slot, making it compatible with
    :class:`~QVideo.lib.QVideoWriter` as a frame source.

    Parameters
    ----------
    fps : float
        Frame rate of the video source [frames per second].
        Stored as an attribute for :class:`~QVideo.lib.QVideoWriter`
        compatibility.
    pos : list[float]
        Initial [x, y] position of the ROI.
    size : list[float]
        Initial [width, height] of the ROI.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~pyqtgraph.RectROI`.

    Signals
    -------
    newFrame : np.ndarray
        Emitted with the cropped frame each time :meth:`crop` is called.
    '''

    newFrame = pyqtSignal(np.ndarray)

    def __init__(self, fps: float, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fps = fps

    @pyqtSlot(np.ndarray)
    def crop(self, frame: np.ndarray) -> None:
        '''Crop *frame* to the current ROI bounds and emit :attr:`newFrame`.

        Parameters
        ----------
        frame : np.ndarray
            Input video frame to crop.
        '''
        x, y = self.pos()
        w, h = self.size()
        crop = frame[int(y):int(y + h), int(x):int(x + w)]
        self.newFrame.emit(crop)


class ROIDemo(QCamcorder):
    '''Camcorder demo with a draggable ROI for recording cropped video.

    Subclasses :class:`~QVideo.QCamcorder.QCamcorder` and overlays a
    resizable :class:`ROIFilter` on the video screen. While recording,
    camera frames are routed through the ROI cropper before being saved
    by the DVR.

    Parameters
    ----------
    cameraTree : QCameraTree
        Camera control tree providing the video source.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~QVideo.QCamcorder.QCamcorder`.

    Attributes
    ----------
    ROI_POS : list[int]
        Default [x, y] position of the ROI overlay. Default: ``[100, 100]``.
    ROI_SIZE : list[int]
        Default [width, height] of the ROI overlay. Default: ``[400, 400]``.
    '''

    ROI_POS: list[int] = [100, 100]
    ROI_SIZE: list[int] = [400, 400]

    def _setupUi(self) -> None:
        super()._setupUi()
        self.roi = ROIFilter(self.source.fps,
                             self.ROI_POS, self.ROI_SIZE,
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
    def recording(self, is_recording: bool) -> None:
        '''Respond to DVR recording state changes.

        Locks the ROI and connects the camera source to the ROI cropper
        when recording starts; unlocks and disconnects when stopped.

        Parameters
        ----------
        is_recording : bool
            ``True`` when the DVR starts recording, ``False`` when stopped.
        '''
        if is_recording:
            self.roi.movable = False
            self.source.newFrame.connect(self.roi.crop)
        else:
            self.roi.movable = True
            self.source.newFrame.disconnect(self.roi.crop)


def main() -> None:  # pragma: no cover
    '''Launch the ROI demo with an interactively chosen camera.'''
    from QVideo.lib import choose_camera

    pg.mkQApp()
    camera = choose_camera().start()
    widget = ROIDemo(camera)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
