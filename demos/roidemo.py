#!/usr/bin/env python3
'''Camcorder demo with a draggable ROI for recording a cropped video region.

Run directly::

    python -m QVideo.demos.roidemo
'''

from qtpy import QtCore
import pyqtgraph as pg
import numpy as np
from pathlib import Path
from QVideo.QCamcorder import QCamcorder
from QVideo.lib import launch
from QVideo.lib.videotypes import FrameInfo


__all__ = ['CropROI', 'ROIDemo']


class CropROI(pg.RectROI):
    '''Draggable rectangular ROI that crops video frames to its bounds.

    Subclasses :class:`pyqtgraph.RectROI` and adds a :attr:`newFrame`
    signal and :meth:`crop` slot, making it compatible with
    :class:`~QVideo.lib.QVideoWriter` as a frame source.  The
    :class:`~QVideo.lib.videotypes.FrameInfo` of each frame passes through
    unchanged, so the recorder keeps the capture times and the backlog
    watch of :class:`~QVideo.dvr.QDVRWidget.QDVRWidget`.  (The filter
    :class:`~QVideo.filters.roi.ROIFilter` crops without a graphical ROI.)
    The crop is a copy, so a queued frame holds only the cropped pixels and
    not the camera frame that they came from.

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
    newFrame : np.ndarray, FrameInfo
        Emitted with the cropped frame each time :meth:`crop` is called.
    '''

    #: Emitted with the cropped frame and its capture information each
    #: time :meth:`crop` is called.
    newFrame = QtCore.Signal(np.ndarray, object)

    def __init__(self, fps: float, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fps = fps

    @QtCore.Slot(np.ndarray, object)
    def crop(self, frame: np.ndarray, info: FrameInfo | None = None) -> None:
        '''Crop *frame* to the current ROI bounds and emit :attr:`newFrame`.

        Parameters
        ----------
        frame : np.ndarray
            Input video frame to crop.
        info : FrameInfo, optional
            Capture information for *frame*, passed on with the crop.
        '''
        x, y = self.pos()
        w, h = self.size()
        crop = frame[int(y):int(y + h), int(x):int(x + w)]
        self.newFrame.emit(crop.copy(), info)


class ROIDemo(QCamcorder):
    '''A camcorder that records only the region inside a draggable ROI.

    Data flow::

        camera -> screen (+ ROI rectangle)
           '----> ROI crop -> recorder, while recording

    Extends :class:`~QVideo.QCamcorder.QCamcorder` with a resizable
    :class:`CropROI` drawn on the video screen.  While recording, the
    ROI is locked and camera frames are cropped to it before the DVR saves
    them.

    Parameters
    ----------
    cameraTree : QCameraTree
        Camera control tree providing the video source.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~QVideo.QCamcorder.QCamcorder`.

    Attributes
    ----------
    DISPLAY_RATE : int
        Maximum display frame rate [fps]. Default: ``30``.
    '''

    DISPLAY_RATE: int = 30

    def _roiGeometry(self) -> tuple[list[int], list[int]]:
        '''Return default ROI position and size for the current source.

        The ROI covers one quarter of the frame area (half each dimension),
        rounded down to the nearest multiple of 8, and centered.

        Returns
        -------
        pos : list[int]
            ``[x, y]`` top-left corner in image pixel coordinates.
        size : list[int]
            ``[width, height]`` in image pixel coordinates.
        '''
        shape = self.source.shape
        w = (shape.width() // 2 // 8) * 8
        h = (shape.height() // 2 // 8) * 8
        x = (shape.width() - w) // 2
        y = (shape.height() - h) // 2
        return [x, y], [w, h]

    def _setupUi(self) -> None:
        super()._setupUi()
        self.screen.framerate = self.DISPLAY_RATE
        pos, size = self._roiGeometry()
        self.roi = CropROI(self.source.fps,
                           pos, size,
                           snapSize=8,
                           scaleSnap=True,
                           sideScalers=True,
                           movable=True,
                           invertible=False,
                           rotatable=False,
                           removable=False)
        self.screen.view.addItem(self.roi)
        self.dvr.filename = str(Path.home() / 'roidemo.avi')
        self.dvr.source = self.roi

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self.dvr.recording.connect(self.recording)

    @QtCore.Slot(bool)
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


if __name__ == '__main__':  # pragma: no cover
    launch(ROIDemo, 'ROI Demo')
