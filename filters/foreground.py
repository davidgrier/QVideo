'''Foreground estimator using MOG2 Gaussian-mixture background model.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image
import cv2
import numpy as np


__all__ = ['ForegroundEstimator', 'QForegroundEstimator']


class ForegroundEstimator(AsyncVideoFilter):

    '''Foreground estimator using OpenCV MOG2 background subtraction.

    Models each pixel as a Gaussian mixture over time to identify a
    persistent background, then returns each frame divided by that
    background.  For a multiplicative image model ``I = B × F`` this
    recovers the foreground modulation ``F ≈ I / B``.

    The output is scaled by *mean* and cast to ``uint8`` so that a
    pixel carrying no foreground modulation (``I ≈ B``) maps to *mean*.
    Pixels brighter than the background map above *mean*; darker pixels
    map below.

    Parameters
    ----------
    history : int
        Number of frames used to build the background model.  Longer
        histories give a more stable estimate but adapt more slowly to
        illumination drift.  Default: ``500``.
    varThreshold : float
        Mahalanobis-distance threshold for classifying a pixel as
        foreground in the MOG2 model.  Smaller values make the
        classifier more sensitive.  Default: ``16.0``.
    mean : float
        Output scale factor.  A pixel where ``frame == background``
        maps to this value in the output.  Default: ``128.0``.

    Notes
    -----
    Changing *history* or *varThreshold* resets the background model,
    which discards accumulated statistics and triggers a re-learning
    phase.
    '''

    def __init__(self,
                 history: int = 500,
                 varThreshold: float = 16.0,
                 mean: float = 128.0) -> None:
        self._history = max(1, int(history))
        self._varThreshold = max(0.0, float(varThreshold))
        self._mean = max(1.0, float(mean))
        self._bgs = cv2.createBackgroundSubtractorMOG2(
            history=self._history,
            varThreshold=self._varThreshold,
            detectShadows=False)
        super().__init__()

    def _newBgs(self) -> None:
        self._bgs = cv2.createBackgroundSubtractorMOG2(
            history=self._history,
            varThreshold=self._varThreshold,
            detectShadows=False)

    @property
    def history(self) -> int:
        '''Frames used to build the background model.'''
        return self._history

    @history.setter
    def history(self, value: int) -> None:
        self._history = max(1, int(value))
        self._newBgs()

    @property
    def varThreshold(self) -> float:
        '''Mahalanobis-distance threshold for foreground classification.'''
        return self._varThreshold

    @varThreshold.setter
    def varThreshold(self, value: float) -> None:
        self._varThreshold = max(0.0, float(value))
        self._newBgs()

    @property
    def mean(self) -> float:
        '''Output scale factor: ratio == 1 maps to this pixel value.'''
        return self._mean

    @mean.setter
    def mean(self, value: float) -> None:
        self._mean = max(1.0, float(value))

    def process(self, image: Image) -> Image:
        '''Divide *image* by the MOG2 background estimate.

        Called in the background thread.

        Parameters
        ----------
        image : Image
            Input frame (grayscale or BGR ``uint8``).

        Returns
        -------
        Image
            Foreground-enhanced frame scaled to ``uint8``.
        '''
        bgs = self._bgs
        bgs.apply(image)
        bg = bgs.getBackgroundImage()
        bg_f = bg.astype(np.float32)
        result = np.zeros(image.shape, dtype=np.float32)
        np.divide(image, bg_f, out=result, where=(bg_f > 0))
        return np.clip(self._mean * result, 0, 255).astype(np.uint8)


class QForegroundEstimator(QVideoFilter):

    display_name = 'Foreground'

    '''Widget for :class:`ForegroundEstimator` with history and threshold spinboxes.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Foreground', ForegroundEstimator())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._historyBox = SpinBox(self, prefix='history: ',
                                   value=self.filter.history,
                                   step=100, int=True)
        self._historyBox.setMinimum(1)
        self._layout.addWidget(self._historyBox)
        self._thresholdBox = SpinBox(self, prefix='threshold: ',
                                     value=self.filter.varThreshold,
                                     step=1.0)
        self._thresholdBox.setMinimum(0.0)
        self._layout.addWidget(self._thresholdBox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._historyBox.valueChanged.connect(self._setHistory)
        self._thresholdBox.valueChanged.connect(self._setThreshold)

    @QtCore.Slot(object)
    def _setHistory(self, value: int) -> None:
        self.filter.history = value
        with QtCore.QSignalBlocker(self._historyBox):
            self._historyBox.setValue(self.filter.history)

    @QtCore.Slot(object)
    def _setThreshold(self, value: float) -> None:
        self.filter.varThreshold = value


if __name__ == '__main__':  # pragma: no cover
    QForegroundEstimator.example()
