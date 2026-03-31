from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import cv2
import logging


logger = logging.getLogger(__name__)

__all__ = ['EdgeFilter', 'QEdgeFilter']


class EdgeFilter(VideoFilter):

    '''Canny edge detector.

    Converts color input to grayscale, then applies OpenCV's Canny
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
            logger.warning(f'low ({low}) must be less than '
                           f'high ({self._high}); ignoring')
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
            logger.warning(f'high ({high}) must be greater than '
                           f'low ({self._low}); ignoring')
            return
        self._high = high

    def add(self, image: Image) -> None:
        '''Convert color input to grayscale and store the result.

        Parameters
        ----------
        image : Image
            Input frame.  3-D (color) arrays are converted to
            grayscale; 2-D arrays are stored unchanged.
        '''
        if image.ndim == 3:
            self.data = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            self.data = image

    def get(self) -> Image | None:
        '''Return the Canny edge map of the stored frame.

        Returns
        -------
        Image or None
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
        super().__init__(parent, 'Canny Edge Detection', EdgeFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._layout.addWidget(QtWidgets.QLabel('low'))
        self._lowSpinbox = SpinBox(self, value=self.filter.low, int=True)
        self._lowSpinbox.setMinimum(1)
        self._lowSpinbox.valueChanged.connect(self.setLow)
        self._layout.addWidget(self._lowSpinbox)
        self._layout.addWidget(QtWidgets.QLabel('high'))
        self._highSpinbox = SpinBox(self, value=self.filter.high, int=True)
        self._highSpinbox.setMinimum(2)
        self._highSpinbox.valueChanged.connect(self.setHigh)
        self._layout.addWidget(self._highSpinbox)

    @QtCore.Slot(object)
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
        self._lowSpinbox.blockSignals(True)
        self._lowSpinbox.setValue(self.filter.low)
        self._lowSpinbox.blockSignals(False)

    @QtCore.Slot(object)
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
        self._highSpinbox.blockSignals(True)
        self._highSpinbox.setValue(self.filter.high)
        self._highSpinbox.blockSignals(False)


if __name__ == '__main__':  # pragma: no cover
    QEdgeFilter.example()
