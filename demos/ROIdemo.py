#!/usr/bin/env python3
'''Camcorder demo with a draggable ROI for recording a cropped video region.

Run directly::

    python -m QVideo.demos.ROIdemo
'''

from qtpy import QtCore
import pyqtgraph as pg
import numpy as np
from pathlib import Path
from QVideo.QCamcorder import QCamcorder


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

    #: Emitted with the cropped frame each time :meth:`crop` is called.
    newFrame = QtCore.Signal(np.ndarray)

    def __init__(self, fps: float, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fps = fps

    @QtCore.Slot(np.ndarray)
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
        self.roi = ROIFilter(self.source.fps,
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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
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


def main() -> None:  # pragma: no cover
    '''Launch the ROI demo with an interactively chosen camera.'''
    from QVideo.lib import choose_camera

    from qtpy import QtGui, QtWidgets
    app = pg.mkQApp('ROI Demo')
    camera = choose_camera().start()
    widget = ROIDemo(camera)
    QtWidgets.QShortcut(
        QtGui.QKeySequence('Ctrl+Q'), widget
    ).activated.connect(app.quit)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
