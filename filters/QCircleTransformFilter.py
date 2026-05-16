'''Orientation alignment transform filter — detects ring-like features.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np
from numpy.typing import NDArray
from scipy.signal import savgol_filter
try:
    from scipy.fft import fft2, ifft2, fftshift
except ImportError:
    from scipy.fftpack import fft2, ifft2, fftshift


__all__ = ['CircleTransformFilter', 'QCircleTransformFilter']


class CircleTransformFilter(AsyncVideoFilter):

    '''Orientation alignment transform (OAT) ring-detection filter.

    Detects circularly symmetric ring-like features by computing the
    orientation alignment transform of Krishnatreya & Grier (2014).
    Each pixel's gradient orientation is compared against the expected
    orientation for a ring centred at every candidate position; the
    result is a detection map whose peaks locate ring centres.

    The transform integrates evidence from all ring radii simultaneously,
    so no radius parameter is required.  Computation runs in a background
    thread via :class:`~QVideo.lib.AsyncVideoFilter.AsyncVideoFilter`.

    Parameters
    ----------
    window : int
        Savitzky-Golay derivative window size [pixels].  Must be odd and
        greater than *polyorder*.  Larger values smooth noise but reduce
        spatial resolution of detected ring centres.  Default: ``13``.
    polyorder : int
        Savitzky-Golay polynomial order.  Must be less than *window*.
        Default: ``3``.

    Notes
    -----
    The OAT kernel :math:`K(\\mathbf{k}) = e^{-2i\\theta_k}/|\\mathbf{k}|`
    is cached by frame shape and recomputed only when the shape changes.

    The output is normalised per-frame to ``[0, 255]`` and returned as
    ``uint8``.  Peak brightness indicates likely ring centres.

    References
    ----------
    B. J. Krishnatreya and D. G. Grier,
    'Fast feature identification for holographic tracking: the
    orientation alignment transform,'
    *Optics Express* **22**, 12773–12778 (2014).
    '''

    def __init__(self, window: int = 13, polyorder: int = 3) -> None:
        self._kernel = np.ones((1, 1))
        self.window = window
        self.polyorder = polyorder
        super().__init__()

    @property
    def window(self) -> int:
        '''Savitzky-Golay derivative window [pixels], always odd and ≥ 3.'''
        return self._window

    @window.setter
    def window(self, window: int) -> None:
        window = max(3, int(window))
        self._window = window + (1 - window % 2)

    @property
    def polyorder(self) -> int:
        '''Savitzky-Golay polynomial order, always ≥ 1.'''
        return self._polyorder

    @polyorder.setter
    def polyorder(self, polyorder: int) -> None:
        self._polyorder = max(1, int(polyorder))

    def _kernel_for(self, shape: tuple[int, int]) -> NDArray:
        if shape == self._kernel.shape:
            return self._kernel
        ny, nx = shape
        kx = fftshift(np.linspace(-1., 1., nx, endpoint=False))
        ky = fftshift(np.linspace(-1., 1., ny, endpoint=False))
        k = np.hypot.outer(ky, kx) + 0.001
        kernel = np.subtract.outer(1.j * ky, kx) / k
        kernel *= kernel / k
        self._kernel = kernel
        return kernel

    def process(self, image: Image) -> Image:
        '''Compute the OAT of *image* and return a uint8 heat map.

        Called in the background thread.  Converts colour input to float
        grayscale, computes orientational order gradients via
        Savitzky-Golay differentiation, then convolves with the OAT kernel
        in Fourier space.

        Parameters
        ----------
        image : Image
            Input frame (grayscale or colour uint8).

        Returns
        -------
        Image
            OAT heat map, same spatial shape as *image*, dtype ``uint8``.
            Bright peaks indicate ring centres.
        '''
        gray = image.mean(axis=2) if image.ndim == 3 else image.astype(float)
        psi = np.empty(gray.shape, dtype=complex)
        psi.real = savgol_filter(gray, self._window, self._polyorder, 1, axis=1)
        psi.imag = savgol_filter(gray, self._window, self._polyorder, 1, axis=0)
        psi *= psi
        psi = fft2(psi, workers=-1, overwrite_x=True)
        psi *= self._kernel_for(gray.shape)
        psi = ifft2(psi, workers=-1, overwrite_x=True)
        c = psi.real ** 2 + psi.imag ** 2
        cmax = c.max()
        if cmax > np.finfo(float).eps:
            c *= 255.0 / cmax
        return c.astype(np.uint8)


class QCircleTransformFilter(QVideoFilter):

    '''Widget for :class:`CircleTransformFilter` with a window spinbox.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Circle Transform', CircleTransformFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._layout.addWidget(QtWidgets.QLabel('window'))
        self._spinbox = SpinBox(value=self.filter.window,
                                step=2, int=True)
        self._spinbox.setMinimum(3)
        self._layout.addWidget(self._spinbox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._spinbox.valueChanged.connect(self._setWindow)

    @QtCore.Slot(object)
    def _setWindow(self, window: int) -> None:
        self.filter.window = window
        with QtCore.QSignalBlocker(self._spinbox):
            self._spinbox.setValue(self.filter.window)


if __name__ == '__main__':  # pragma: no cover
    QCircleTransformFilter.example()
