'''Binary threshold filter.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np
import cv2

__all__ = ['ThresholdFilter', 'QThresholdFilter']


class ThresholdFilter(VideoFilter):

    '''Binary threshold filter.

    Converts a grayscale frame to a binary image: pixels above
    *threshold* become 255 (white) and pixels at or below it become 0
    (black).

    Parameters
    ----------
    threshold : int
        Threshold value in the range [0, 255].  Values outside this
        range are clamped.  Default: ``127``.

    Notes
    -----
    Thresholding is performed by :func:`cv2.threshold` with
    ``cv2.THRESH_BINARY``.  The input frame should be a single-channel
    uint8 image.
    '''

    def __init__(self, threshold: int = 127) -> None:
        super().__init__()
        self.threshold = threshold

    @property
    def threshold(self) -> int:
        '''Threshold value [0, 255], clamped on assignment.'''
        return self._threshold

    @threshold.setter
    def threshold(self, threshold: int) -> None:
        self._threshold = int(np.clip(threshold, 0, 255))

    def get(self) -> Image | None:
        '''Return the thresholded frame.

        Returns
        -------
        Image or None
            Binary version of the most recently added frame, or
            ``None`` if no frame has been added yet.
        '''
        if self.data is None:
            return None
        _, thresh = cv2.threshold(
            self.data, self.threshold, 255, cv2.THRESH_BINARY)
        return thresh


class QThresholdFilter(QVideoFilter):

    '''Widget for :class:`ThresholdFilter` with a threshold spinbox.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Threshold', ThresholdFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._layout.addWidget(QtWidgets.QLabel('threshold:'))
        self._spinbox = SpinBox(value=self.filter.threshold,
                                bounds=(0, 255), int=True)
        self._spinbox.valueChanged.connect(self.setThreshold)
        self._layout.addWidget(self._spinbox)

    @QtCore.Slot(object)
    def setThreshold(self, value: int) -> None:
        '''Set the threshold value.

        Passes *value* to :class:`ThresholdFilter`, which clamps it to
        [0, 255], then snaps the spinbox to the corrected value.

        Parameters
        ----------
        value : int
            New threshold.  Values outside [0, 255] are clamped.
        '''
        self.filter.threshold = value
        with QtCore.QSignalBlocker(self._spinbox):
            self._spinbox.setValue(self.filter.threshold)


if __name__ == '__main__':  # pragma: no cover
    QThresholdFilter.example()
