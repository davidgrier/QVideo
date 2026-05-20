'''Dejitter filter using phase-correlation image stabilization.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np
import cv2


__all__ = ['DejitterFilter', 'QDejitterFilter']


class DejitterFilter(AsyncVideoFilter):

    '''Translation-only video stabilizer using phase correlation.

    Estimates the per-frame shift of the camera relative to a reference
    image via ``cv2.phaseCorrelate`` (FFT-based cross-correlation) and
    corrects it with ``cv2.warpAffine``.

    Two reference-update modes are supported:

    - **static**: the reference is the first frame seen after
      construction or :meth:`reset`.  All subsequent frames are aligned
      to that fixed origin.  Best for suppressing mechanical vibration
      around a fixed position.
    - **rolling**: the reference is updated each frame by an exponential
      moving average (weight *alpha* on the new frame).  The reference
      therefore tracks slow drift, so only fast jitter is corrected.
      Best for long acquisitions where deliberate stage motion should be
      preserved.

    A Hanning window is applied before phase correlation to reduce
    spectral leakage.

    Parameters
    ----------
    mode : str
        Reference update mode: ``'static'`` or ``'rolling'``.
        Default: ``'static'``.
    alpha : float
        EMA weight on the incoming frame for rolling-mode reference
        updates.  Clamped to ``(0, 1]``.  Ignored in static mode.
        Default: ``0.05``.
    '''

    MODES = ('static', 'rolling')

    def __init__(self,
                 mode: str = 'static',
                 alpha: float = 0.05) -> None:
        if mode not in self.MODES:
            raise ValueError(f'mode must be one of {self.MODES}')
        self._mode = mode
        self._alpha = float(np.clip(alpha, 1e-6, 1.0))
        self._reference: np.ndarray | None = None
        self._window: np.ndarray | None = None
        super().__init__()

    @property
    def mode(self) -> str:
        '''Reference update mode; one of :attr:`MODES`.'''
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value not in self.MODES:
            raise ValueError(f'mode must be one of {self.MODES}')
        if value != self._mode:
            self._mode = value
            self.reset()

    @property
    def alpha(self) -> float:
        '''EMA weight on incoming frame for rolling reference, in ``(0, 1]``.'''
        return self._alpha

    @alpha.setter
    def alpha(self, value: float) -> None:
        self._alpha = float(np.clip(value, 1e-6, 1.0))

    def reset(self) -> None:
        '''Clear the reference frame and restart stabilization.'''
        self._reference = None
        self._window = None
        self._result = None

    def process(self, image: Image) -> Image:
        '''Estimate and correct the translational shift of *image*.

        Called in the background thread.  The first frame after
        construction or :meth:`reset` seeds the reference and is
        returned unchanged.

        Parameters
        ----------
        image : Image
            Input frame (grayscale or BGR ``uint8``).

        Returns
        -------
        Image
            Stabilized frame with the same shape and dtype as *image*.
        '''
        h, w = image.shape[:2]
        gray = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
                if image.ndim == 3 else image.astype(np.float32))

        if self._reference is None or self._reference.shape != gray.shape:
            self._reference = gray.copy()
            self._window = cv2.createHanningWindow((w, h), cv2.CV_32F)
            return image

        (dx, dy), _ = cv2.phaseCorrelate(self._reference.copy(), gray.copy(),
                                          self._window.copy())

        M = np.float32([[1, 0, -dx], [0, 1, -dy]])
        corrected = cv2.warpAffine(image, M, (w, h))

        if self._mode == 'rolling':
            self._reference += self._alpha * (gray - self._reference)

        return corrected


class QDejitterFilter(QVideoFilter):

    '''Widget for :class:`DejitterFilter` with mode selector, alpha spinbox,
    and a reset button.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Dejitter'
    display_category = 'Preprocessing'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Dejitter', DejitterFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._modeBox = QtWidgets.QComboBox()
        self._modeBox.addItems(['Static', 'Rolling'])
        self._layout.addWidget(self._modeBox)
        self._alphaBox = SpinBox(value=self.filter.alpha,
                                 bounds=(1e-6, 1.0), step=0.05,
                                 prefix='α ')
        self._alphaBox.setVisible(False)
        self._layout.addWidget(self._alphaBox)
        self._resetButton = QtWidgets.QPushButton('Reset')
        self._layout.addWidget(self._resetButton)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._modeBox.currentTextChanged.connect(self._setMode)
        self._alphaBox.valueChanged.connect(self._setAlpha)
        self._resetButton.clicked.connect(self._resetReference)

    @QtCore.Slot(str)
    def _setMode(self, text: str) -> None:
        mode = text.lower()
        self.filter.mode = mode
        self._alphaBox.setVisible(mode == 'rolling')

    @QtCore.Slot(object)
    def _setAlpha(self, value: float) -> None:
        self.filter.alpha = value

    @QtCore.Slot()
    def _resetReference(self) -> None:
        self.filter.reset()


if __name__ == '__main__':  # pragma: no cover
    QDejitterFilter.example()
