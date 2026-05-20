'''Gamma intensity-correction filter and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np
import cv2

__all__ = ['GammaFilter', 'QGammaFilter']


class GammaFilter(VideoFilter):

    '''Gamma intensity correction.

    Applies the power-law transform

    .. math::

       \\text{output} = \\left(\\frac{\\text{input}}{255}\\right)^{\\gamma}
       \\times 255

    to every pixel.  *γ* < 1 brightens the image (lifts shadows); *γ* > 1
    darkens it (deepens shadows); *γ* = 1 is the identity.

    The transform is implemented as a 256-entry look-up table built once
    when :attr:`gamma` changes, so per-frame cost is a single table lookup
    regardless of image size.  The same LUT is applied to every channel,
    preserving color balance.

    Parameters
    ----------
    gamma : float
        Power-law exponent.  Must be ≥ 0.1.  Default: ``1.0``.
    '''

    def __init__(self, gamma: float = 1.0) -> None:
        super().__init__()
        self.gamma = gamma

    @property
    def gamma(self) -> float:
        '''Power-law exponent (≥ 0.1); LUT is rebuilt on assignment.'''
        return self._gamma

    @gamma.setter
    def gamma(self, value: float) -> None:
        self._gamma = max(0.1, float(value))
        table = np.arange(256, dtype=np.float32) / 255.0
        self._lut = np.clip(
            np.power(table, self._gamma) * 255.0, 0, 255).astype(np.uint8)

    def get(self) -> Image | None:
        '''Return the gamma-corrected frame.

        Returns
        -------
        Image or None
            Corrected uint8 image, or ``None`` if no frame has been added.
        '''
        if self.data is None:
            return None
        return cv2.LUT(self.data, self._lut)

    def to_code(self) -> 'FilterCode':
        from QVideo.lib.QVideoFilter import FilterCode
        return FilterCode(
            imports=frozenset({'import numpy as np'}),
            lines=[
                f'image = np.clip(np.power(image.astype(np.float32) / 255.0,'
                f' {self._gamma}) * 255.0, 0, 255).astype(np.uint8)',
            ],
            comment=f'gamma correction, γ={self._gamma}',
        )


class QGammaFilter(QVideoFilter):

    '''Widget for :class:`GammaFilter` with a gamma spinbox.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Gamma Correction'
    display_category = 'Preprocessing'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Gamma Correction', GammaFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._layout.addWidget(QtWidgets.QLabel('γ'))
        self._gammaBox = SpinBox(value=self.filter.gamma,
                                 bounds=(0.1, 10.0), step=0.1)
        self._layout.addWidget(self._gammaBox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._gammaBox.valueChanged.connect(self._setGamma)

    @QtCore.Slot(object)
    def _setGamma(self, value: float) -> None:
        self.filter.gamma = value


if __name__ == '__main__':  # pragma: no cover
    QGammaFilter.example()
