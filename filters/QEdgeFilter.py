from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.VideoFilter import QVideoFilter, VideoFilter
import numpy as np
import cv2
import logging


logger = logging.getLogger(__name__)

__all__ = ['EdgeFilter', 'QEdgeFilter']


class EdgeFilter(VideoFilter):

    '''Canny edge detector.

    Converts colour input to greyscale, then applies OpenCV's Canny
    edge-detection algorithm.

    Parameters
    ----------
    low : int
        Lower hysteresis threshold.  Must be at least 1 and strictly
        less than *high*.  Default: ``50``.
    high : int
        Upper hysteresis threshold.  Must be at least 2 and strictly
        greater than *low*.  Default: ``150``.

    Notes
    -----
    Both thresholds are passed directly to :func:`cv2.Canny`.  OpenCV
    recommends a 2:1 or 3:1 high-to-low ratio for typical images.
    '''

    def __init__(self, low: int = 50, high: int = 150) -> None:
        super().__init__()
        self._low = 1
        self._high = 2
        self.high = high
        self.low = low

    @property
    def low(self) -> int:
        '''Lower Canny threshold (≥ 1, < high).'''
        return self._low

    @low.setter
    def low(self, low: int) -> None:
        low = max(1, int(low))
        if low >= self._high:
            logger.warning('low (%d) must be less than high (%d); '
                           'ignoring', low, self._high)
            return
        self._low = low

    @property
    def high(self) -> int:
        '''Upper Canny threshold (≥ 2, > low).'''
        return self._high

    @high.setter
    def high(self, high: int) -> None:
        high = max(2, int(high))
        if high <= self._low:
            logger.warning('high (%d) must be greater than low (%d); '
                           'ignoring', high, self._low)
            return
        self._high = high

    def add(self, image: np.ndarray) -> None:
        '''Convert colour input to greyscale and store the result.

        Parameters
        ----------
        image : np.ndarray
            Input frame.  3-D (colour) arrays are converted to
            greyscale; 2-D arrays are stored unchanged.
        '''
        if image.ndim == 3:
            self.data = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            self.data = image

    def get(self) -> np.ndarray | None:
        '''Return the Canny edge map of the stored frame.

        Returns
        -------
        np.ndarray or None
            Edge map, or ``None`` if no frame has been added yet.
        '''
        if self.data is None:
            return None
        return cv2.Canny(self.data, self.low, self.high)


class QEdgeFilter(QVideoFilter):

    '''Widget for :class:`EdgeFilter` with low- and high-threshold spinboxes.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__('Canny Edge Detection', parent, EdgeFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self.layout.addWidget(QtWidgets.QLabel('low'))
        self._low_spinbox = SpinBox(self, value=self.filter.low, int=True)
        self._low_spinbox.setMinimum(1)
        self._low_spinbox.valueChanged.connect(self.setLow)
        self.layout.addWidget(self._low_spinbox)
        self.layout.addWidget(QtWidgets.QLabel('high'))
        self._high_spinbox = SpinBox(self, value=self.filter.high, int=True)
        self._high_spinbox.setMinimum(2)
        self._high_spinbox.valueChanged.connect(self.setHigh)
        self.layout.addWidget(self._high_spinbox)

    @QtCore.pyqtSlot(object)
    def setLow(self, low: int) -> None:
        '''Set the lower Canny threshold.

        Passes *low* to :class:`EdgeFilter`, which enforces the
        constraint ``low < high``, then snaps the spinbox to the
        accepted value.

        Parameters
        ----------
        low : int
            New lower threshold.
        '''
        self.filter.low = low
        self._low_spinbox.blockSignals(True)
        self._low_spinbox.setValue(self.filter.low)
        self._low_spinbox.blockSignals(False)

    @QtCore.pyqtSlot(object)
    def setHigh(self, high: int) -> None:
        '''Set the upper Canny threshold.

        Passes *high* to :class:`EdgeFilter`, which enforces the
        constraint ``high > low``, then snaps the spinbox to the
        accepted value.

        Parameters
        ----------
        high : int
            New upper threshold.
        '''
        self.filter.high = high
        self._high_spinbox.blockSignals(True)
        self._high_spinbox.setValue(self.filter.high)
        self._high_spinbox.blockSignals(False)


if __name__ == '__main__':  # pragma: no cover
    QEdgeFilter.example()
