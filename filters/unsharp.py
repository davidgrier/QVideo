'''Unsharp masking filter and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import cv2

__all__ = ['UnsharpFilter', 'QUnsharpFilter']


class UnsharpFilter(VideoFilter):

    '''Unsharp mask sharpening.

    Computes a Gaussian-blurred copy of the frame and blends it with the
    original to emphasise high-frequency detail:

    .. math::

       \\text{output} = (1 + \\alpha)\\,\\text{image}
                      - \\alpha\\,\\text{blur}(\\text{image},\\,\\sigma)

    where *σ* (*radius*) sets the blur width and *α* (*amount*) controls
    sharpening strength.  ``cv2.addWeighted`` is used so the result is
    clipped to ``[0, 255]`` and returned as ``uint8``.

    Parameters
    ----------
    radius : float
        Standard deviation of the Gaussian blur [pixels] (≥ 0.1).
        Larger values sharpen broader features.  Default: ``2.0``.
    amount : float
        Sharpening strength (≥ 0.0).  ``0`` is a no-op; ``1`` gives
        a standard unsharp mask; higher values over-sharpen.
        Default: ``1.0``.
    '''

    def __init__(self,
                 radius: float = 2.0,
                 amount: float = 1.0) -> None:
        super().__init__()
        self.radius = radius
        self.amount = amount

    @property
    def radius(self) -> float:
        '''Gaussian blur σ [pixels] (≥ 0.1).'''
        return self._radius

    @radius.setter
    def radius(self, value: float) -> None:
        self._radius = max(0.1, float(value))

    @property
    def amount(self) -> float:
        '''Sharpening strength (≥ 0.0).'''
        return self._amount

    @amount.setter
    def amount(self, value: float) -> None:
        self._amount = max(0.0, float(value))

    def get(self) -> Image | None:
        '''Return the sharpened frame.

        Returns
        -------
        Image or None
            uint8 sharpened image, or ``None`` if no frame has been added.
        '''
        if self.data is None:
            return None
        blurred = cv2.GaussianBlur(self.data, (0, 0), self._radius)
        return cv2.addWeighted(self.data, 1 + self._amount,
                               blurred, -self._amount, 0)

    def to_code(self) -> 'FilterCode':
        from QVideo.lib.QVideoFilter import FilterCode
        return FilterCode(
            imports=frozenset({'import cv2'}),
            lines=[
                f'_blurred = cv2.GaussianBlur(image, (0, 0), {self._radius})',
                f'image = cv2.addWeighted(image, {1 + self._amount:.4g}, '
                f'_blurred, {-self._amount:.4g}, 0)',
            ],
            comment=f'unsharp mask, σ={self._radius}, amount={self._amount}',
        )


class QUnsharpFilter(QVideoFilter):

    '''Widget for :class:`UnsharpFilter` with radius and amount spinboxes.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Unsharp Mask'
    display_category = 'Preprocessing'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Unsharp Mask', UnsharpFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._radiusBox = SpinBox(value=self.filter.radius,
                                  bounds=(0.1, 20.0), step=0.5,
                                  prefix='σ ')
        self._layout.addWidget(self._radiusBox)
        self._amountBox = SpinBox(value=self.filter.amount,
                                  bounds=(0.0, 10.0), step=0.1,
                                  prefix='amount ')
        self._layout.addWidget(self._amountBox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._radiusBox.valueChanged.connect(self._setRadius)
        self._amountBox.valueChanged.connect(self._setAmount)

    @QtCore.Slot(object)
    def _setRadius(self, value: float) -> None:
        self.filter.radius = value

    @QtCore.Slot(object)
    def _setAmount(self, value: float) -> None:
        self.filter.amount = value


if __name__ == '__main__':  # pragma: no cover
    QUnsharpFilter.example()
