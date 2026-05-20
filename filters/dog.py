'''Difference-of-Gaussians bandpass filter and companion Qt widget.'''
import logging
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np
import cv2

__all__ = ['DoGFilter', 'QDoGFilter']

logger = logging.getLogger(__name__)


class DoGFilter(VideoFilter):

    '''Difference-of-Gaussians (DoG) bandpass filter.

    Subtracts a wide Gaussian blur from a narrow one, suppressing both
    slowly-varying background (*low_sigma*) and high-frequency noise
    (*high_sigma* sets the noise cutoff).  The result is displayed as the
    absolute value scaled to ``uint8``, so both positive and negative
    excursions appear bright.

    DoG is the standard preprocessing step for particle tracking and
    fluorescence microscopy: it isolates features at the scale set by
    *low_sigma* while removing background and pixel noise.

    Color input is converted to grayscale before filtering.

    Parameters
    ----------
    low_sigma : float
        Standard deviation of the narrower Gaussian [pixels].  Controls the
        smallest feature scale retained.  Must be < *high_sigma*.
        Default: ``1.0``.
    high_sigma : float
        Standard deviation of the wider Gaussian [pixels].  Controls the
        largest background scale removed.  Must be > *low_sigma*.
        Default: ``3.0``.
    '''

    def __init__(self,
                 low_sigma: float = 1.0,
                 high_sigma: float = 3.0) -> None:
        super().__init__()
        self._low_sigma = 0.1
        self._high_sigma = 0.2
        self.high_sigma = high_sigma
        self.low_sigma = low_sigma

    @property
    def low_sigma(self) -> float:
        '''Narrow Gaussian σ [pixels]; must be < :attr:`high_sigma`.'''
        return self._low_sigma

    @low_sigma.setter
    def low_sigma(self, value: float) -> None:
        value = max(0.1, float(value))
        if value >= self._high_sigma:
            logger.warning(
                f'low_sigma ({value}) must be less than '
                f'high_sigma ({self._high_sigma}); ignoring')
            return
        self._low_sigma = value

    @property
    def high_sigma(self) -> float:
        '''Wide Gaussian σ [pixels]; must be > :attr:`low_sigma`.'''
        return self._high_sigma

    @high_sigma.setter
    def high_sigma(self, value: float) -> None:
        value = max(0.2, float(value))
        if value <= self._low_sigma:
            logger.warning(
                f'high_sigma ({value}) must be greater than '
                f'low_sigma ({self._low_sigma}); ignoring')
            return
        self._high_sigma = value

    def get(self) -> Image | None:
        '''Return the DoG-filtered frame.

        Returns
        -------
        Image or None
            uint8 image of the absolute DoG response, or ``None`` if no
            frame has been added.
        '''
        if self.data is None:
            return None
        gray = (self.data.mean(axis=2).astype(np.float32)
                if self.data.ndim == 3 else self.data.astype(np.float32))
        lo = cv2.GaussianBlur(gray, (0, 0), self._low_sigma)
        hi = cv2.GaussianBlur(gray, (0, 0), self._high_sigma)
        return cv2.convertScaleAbs(lo - hi)

    def to_code(self) -> 'FilterCode':
        from QVideo.lib.QVideoFilter import FilterCode
        return FilterCode(
            imports=frozenset({'import cv2', 'import numpy as np'}),
            lines=[
                'if image.ndim == 3:',
                '    image = image.mean(axis=2).astype(np.float32)',
                'else:',
                '    image = image.astype(np.float32)',
                f'_lo = cv2.GaussianBlur(image, (0, 0), {self._low_sigma})',
                f'_hi = cv2.GaussianBlur(image, (0, 0), {self._high_sigma})',
                'image = cv2.convertScaleAbs(_lo - _hi)',
            ],
            comment=f'DoG bandpass, σ_low={self._low_sigma}, σ_high={self._high_sigma}',
        )


class QDoGFilter(QVideoFilter):

    '''Widget for :class:`DoGFilter` with low and high sigma spinboxes.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Difference of Gaussians'
    display_category = 'Preprocessing'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Difference of Gaussians', DoGFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._lowBox = SpinBox(value=self.filter.low_sigma,
                               bounds=(0.1, None), step=0.5,
                               prefix='σ_low ')
        self._layout.addWidget(self._lowBox)
        self._highBox = SpinBox(value=self.filter.high_sigma,
                                bounds=(0.2, None), step=0.5,
                                prefix='σ_high ')
        self._layout.addWidget(self._highBox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._lowBox.valueChanged.connect(self._setLowSigma)
        self._highBox.valueChanged.connect(self._setHighSigma)

    @QtCore.Slot(object)
    def _setLowSigma(self, value: float) -> None:
        self.filter.low_sigma = value
        with QtCore.QSignalBlocker(self._lowBox):
            self._lowBox.setValue(self.filter.low_sigma)

    @QtCore.Slot(object)
    def _setHighSigma(self, value: float) -> None:
        self.filter.high_sigma = value
        with QtCore.QSignalBlocker(self._highBox):
            self._highBox.setValue(self.filter.high_sigma)


if __name__ == '__main__':  # pragma: no cover
    QDoGFilter.example()
