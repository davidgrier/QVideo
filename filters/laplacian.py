'''Laplacian edge-detection filter and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np
import cv2

__all__ = ['LaplacianFilter', 'QLaplacianFilter']


class LaplacianFilter(VideoFilter):

    '''Laplacian (∇²) edge detector with optional Gaussian pre-blur.

    Converts each frame to grayscale, optionally applies a Gaussian blur
    to reduce noise sensitivity, then computes the discrete Laplacian.
    The absolute value is returned as a uint8 image; edges appear bright
    at intensity transitions.

    Setting *sigma* > 0 implements the Laplacian-of-Gaussian (LoG)
    operator.

    Parameters
    ----------
    ksize : int
        Laplacian kernel size [pixels].  Must be odd and ≥ 1.
        Default: ``3``.
    sigma : float
        Standard deviation of the optional Gaussian pre-blur [pixels].
        ``0`` skips blurring.  Default: ``0``.
    '''

    def __init__(self,
                 ksize: int = 3,
                 sigma: float = 0.0) -> None:
        super().__init__()
        self.ksize = ksize
        self.sigma = sigma

    @property
    def ksize(self) -> int:
        '''Laplacian kernel size [pixels], always odd and ≥ 1.'''
        return self._ksize

    @ksize.setter
    def ksize(self, value: int) -> None:
        value = max(1, int(value))
        self._ksize = value + (1 - value % 2)

    @property
    def sigma(self) -> float:
        '''Gaussian pre-blur standard deviation [pixels]; 0 skips blur.'''
        return self._sigma

    @sigma.setter
    def sigma(self, value: float) -> None:
        self._sigma = max(0.0, float(value))

    def to_code(self) -> 'FilterCode':
        from QVideo.lib.QVideoFilter import FilterCode
        lines = [
            'if image.ndim == 3:',
            '    image = image.mean(axis=2).astype(np.uint8)',
        ]
        imports = frozenset({'import cv2', 'import numpy as np'})
        if self._sigma > 0:
            lines.append(f'image = cv2.GaussianBlur(image, (0, 0), {self._sigma})')
        lines.append(
            f'image = cv2.convertScaleAbs(cv2.Laplacian(image, cv2.CV_32F, ksize={self._ksize}))'
        )
        suffix = f', σ={self._sigma}' if self._sigma > 0 else ''
        return FilterCode(
            imports=imports,
            lines=lines,
            comment=f'Laplacian edges, k={self._ksize}{suffix}',
        )

    def get(self) -> Image | None:
        '''Return the Laplacian edge map of the stored frame.

        Returns
        -------
        Image or None
            uint8 edge map, or ``None`` if no frame has been added.
        '''
        if self.data is None:
            return None
        gray = (self.data.mean(axis=2).astype(np.uint8)
                if self.data.ndim == 3 else self.data)
        if self._sigma > 0:
            gray = cv2.GaussianBlur(gray, (0, 0), self._sigma)
        result = cv2.Laplacian(gray, cv2.CV_32F, ksize=self._ksize)
        return cv2.convertScaleAbs(result)


class QLaplacianFilter(QVideoFilter):

    display_name = 'Laplacian'
    display_category = 'Edge Detection'

    '''Widget for :class:`LaplacianFilter` with kernel size and sigma spinboxes.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Laplacian Edge Detection', LaplacianFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._ksizeBox = SpinBox(value=self.filter.ksize,
                                 bounds=(1, None), step=2, int=True,
                                 prefix='k ')
        self._layout.addWidget(self._ksizeBox)
        self._sigmaBox = SpinBox(value=self.filter.sigma,
                                 bounds=(0, None), step=0.5,
                                 prefix='σ ')
        self._layout.addWidget(self._sigmaBox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._ksizeBox.valueChanged.connect(self._setKsize)
        self._sigmaBox.valueChanged.connect(self._setSigma)

    @QtCore.Slot(object)
    def _setKsize(self, value: int) -> None:
        self.filter.ksize = value
        with QtCore.QSignalBlocker(self._ksizeBox):
            self._ksizeBox.setValue(self.filter.ksize)

    @QtCore.Slot(object)
    def _setSigma(self, value: float) -> None:
        self.filter.sigma = value


if __name__ == '__main__':  # pragma: no cover
    QLaplacianFilter.example()
