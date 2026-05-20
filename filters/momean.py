'''Exponential moving-average background estimator and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np
import cv2


__all__ = ['MoMean', 'QMoMean']


class MoMean(VideoFilter):

    '''Exponential moving-average (EMA) background estimator.

    Maintains a per-pixel running average that weights each incoming
    frame by *alpha* and the existing estimate by *(1 − alpha)*:

    .. math::

       \\hat{B}_t = \\alpha\\,I_t + (1 - \\alpha)\\,\\hat{B}_{t-1}

    where :math:`I_t` is the current frame and :math:`\\hat{B}` is the
    background estimate.  A small *alpha* produces a slow-responding,
    heavily smoothed estimate; *alpha = 1* reduces to a passthrough.

    The effective time constant in frames is approximately
    :math:`1 / \\alpha`.

    Parameters
    ----------
    alpha : float
        EMA weight on the incoming frame.  Clamped to ``(0, 1]``.
        Default: ``0.1``.
    '''

    def __init__(self, alpha: float = 0.1) -> None:
        super().__init__()
        self.alpha = alpha
        self._acc: np.ndarray | None = None

    @property
    def alpha(self) -> float:
        '''EMA weight on the incoming frame, in ``(0, 1]``.'''
        return self._alpha

    @alpha.setter
    def alpha(self, value: float) -> None:
        self._alpha = float(np.clip(value, 1e-6, 1.0))

    def reset(self) -> None:
        '''Clear the accumulator and restart the estimator.'''
        self._acc = None
        self.data = None

    def add(self, data: Image) -> None:
        '''Incorporate a new frame into the running average.

        Parameters
        ----------
        data : Image
            Input frame.  If the shape differs from the previous frame
            the accumulator is re-initialised.
        '''
        if self._acc is None or data.shape != self._acc.shape[:len(data.shape)]:
            self._acc = data.astype(np.float32)
        else:
            cv2.accumulateWeighted(data, self._acc, self._alpha)
        self.data = data

    def get(self) -> Image | None:
        '''Return the current background estimate.

        Returns
        -------
        Image or None
            uint8 estimate, or ``None`` if no frames have been added.
        '''
        if self._acc is None:
            return None
        return np.clip(self._acc, 0, 255).astype(np.uint8)


class QMoMean(QVideoFilter):

    '''Widget for :class:`MoMean` with an alpha spinbox.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Running Mean'
    display_category = 'Background'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Running Mean', MoMean())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._alphaBox = SpinBox(value=self.filter.alpha,
                                 bounds=(1e-6, 1.0), step=0.05,
                                 prefix='α ')
        self._layout.addWidget(self._alphaBox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._alphaBox.valueChanged.connect(self._setAlpha)

    @QtCore.Slot(object)
    def _setAlpha(self, value: float) -> None:
        self.filter.alpha = value


if __name__ == '__main__':  # pragma: no cover
    QMoMean.example()
