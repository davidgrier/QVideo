'''Binary threshold filter with global, Otsu, and adaptive methods.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import (VideoFilter, QVideoFilter, FilterCode,
                                       GRAY_LINES)
from QVideo.lib.videotypes import Image
from QVideo.lib.imageops import grayscale
import numpy as np
import cv2
from typing import ClassVar

__all__ = ['ThresholdFilter', 'QThresholdFilter']


class ThresholdFilter(VideoFilter):

    '''Binary threshold filter supporting global, Otsu, and adaptive methods.

    Converts each frame to a binary image using one of four methods:

    - **Global**: pixels above *threshold* become 255, others become 0.
    - **Otsu**: threshold level chosen automatically to minimize intra-class
      variance (Otsu 1979).  The *threshold* parameter is ignored.
    - **Adaptive Mean**: threshold at each pixel is the mean of the
      *block_size* × *block_size* neighborhood minus *C*.
    - **Adaptive Gaussian**: threshold at each pixel is the
      Gaussian-weighted mean of the neighborhood minus *C*.

    Color input is converted to grayscale before thresholding.

    Parameters
    ----------
    threshold : int
        Global threshold value [0, 255].  Default: ``127``.
    method : str
        One of ``'Global'``, ``'Otsu'``, ``'Adaptive Mean'``,
        ``'Adaptive Gaussian'``.  Default: ``'Global'``.
    block_size : int
        Neighborhood size for adaptive methods [pixels].  Must be odd
        and ≥ 3.  Default: ``11``.
    C : int
        Constant subtracted from the adaptive mean.  Default: ``2``.
    '''

    METHODS = ('Global', 'Otsu', 'Adaptive Mean', 'Adaptive Gaussian')

    @property
    def deep(self) -> bool:     # type: ignore[override]
        '''Whether the filter keeps the scale of a ``uint16`` frame.

        The global threshold does, at the same fraction of the range as
        for 8 bits.  OpenCV's Otsu and adaptive methods take 8 bits only,
        so they get the 8 bit copy.
        '''
        return self._method == 'Global'

    #: The OpenCV adaptive method (ADAPTIVE_THRESH_<name>_C) of each
    #: adaptive method.
    _ADAPTIVE: ClassVar[dict[str, str]] = {
        'Adaptive Mean': 'MEAN', 'Adaptive Gaussian': 'GAUSSIAN'}

    def __init__(self,
                 threshold: int = 127,
                 method: str = 'Global',
                 block_size: int = 11,
                 C: int = 2) -> None:
        super().__init__()
        self.threshold = threshold
        self.method = method
        self.block_size = block_size
        self.C = C

    @property
    def threshold(self) -> int:
        '''Global threshold value [0, 255], clamped on assignment.'''
        return self._threshold

    @threshold.setter
    def threshold(self, value: int) -> None:
        self._threshold = int(np.clip(value, 0, 255))

    @property
    def method(self) -> str:
        '''Thresholding method; one of :attr:`METHODS`.'''
        return self._method

    @method.setter
    def method(self, method: str) -> None:
        if method not in self.METHODS:
            raise ValueError(f'unknown method: {method!r}')
        self._method = method

    @property
    def block_size(self) -> int:
        '''Adaptive neighborhood size [pixels], always odd and ≥ 3.'''
        return self._block_size

    @block_size.setter
    def block_size(self, size: int) -> None:
        size = max(3, int(size))
        self._block_size = size + (1 - size % 2)

    @property
    def C(self) -> int:
        '''Constant subtracted from the adaptive neighborhood mean.'''
        return self._C

    @C.setter
    def C(self, value: int) -> None:
        self._C = int(value)

    def to_code(self) -> FilterCode:
        t, block, C = self._threshold, self._block_size, self._C
        steps = {
            'Global': (
                f'image = cv2.threshold(image, {t}, 255, '
                'cv2.THRESH_BINARY)[1]',
                f'global threshold, level={t}'),
            'Otsu': (
                'image = cv2.threshold(image, 0, 255, '
                'cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]',
                'Otsu threshold'),
        }
        if self._method in steps:
            line, comment = steps[self._method]
        else:
            kind = self._ADAPTIVE[self._method]
            line = (f'image = cv2.adaptiveThreshold(image, 255, '
                    f'cv2.ADAPTIVE_THRESH_{kind}_C, '
                    f'cv2.THRESH_BINARY, {block}, {C})')
            comment = (f'{self._method.lower()} threshold, '
                       f'block={block}, C={C}')
        return FilterCode(
            imports={'import cv2'},
            lines=[*GRAY_LINES, line],
            comment=comment,
        )

    def get(self) -> Image | None:
        '''Return the thresholded frame.

        Returns
        -------
        Image or None
            Binary uint8 image, or ``None`` if no frame has been added.
        '''
        if self.data is None:
            return None
        gray = grayscale(self.data)
        if self._method == 'Global':
            if gray.dtype == np.uint16:
                black, white = self.bounds(gray)
                level = black + self._threshold / 255. * (white - black)
                return np.where(gray > level, np.uint16(white),
                                np.uint16(0))
            return cv2.threshold(
                gray, self._threshold, 255, cv2.THRESH_BINARY)[1]
        if self._method == 'Otsu':
            return cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        kind = self._ADAPTIVE[self._method]
        method = getattr(cv2, f'ADAPTIVE_THRESH_{kind}_C')
        return cv2.adaptiveThreshold(
            gray, 255, method, cv2.THRESH_BINARY, self._block_size, self._C)



class QThresholdFilter(QVideoFilter):

    '''Widget for :class:`ThresholdFilter` with method selector and
    context-sensitive parameter spinboxes.

    Shows a method combobox and, depending on the selected method:

    - **Global**: a *level* spinbox [0, 255].
    - **Otsu**: no extra controls (threshold is computed automatically).
    - **Adaptive Mean / Adaptive Gaussian**: *block* (neighborhood size)
      and *C* (subtracted constant) spinboxes.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Threshold'
    display_category = 'Segmentation'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Threshold', ThresholdFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._methodBox = QtWidgets.QComboBox()
        self._methodBox.addItems(ThresholdFilter.METHODS)
        self._layout.addWidget(self._methodBox)
        self._levelBox = SpinBox(value=self.videoFilter.threshold,
                                 bounds=(0, 255), int=True, prefix='level ')
        self._layout.addWidget(self._levelBox)
        self._blockBox = SpinBox(value=self.videoFilter.block_size,
                                 bounds=(3, None), step=2, int=True,
                                 prefix='block ')
        self._layout.addWidget(self._blockBox)
        self._cBox = SpinBox(value=self.videoFilter.C, int=True, prefix='C ')
        self._layout.addWidget(self._cBox)
        self._blockBox.setVisible(False)
        self._cBox.setVisible(False)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._methodBox.currentTextChanged.connect(self._setMethod)
        self._levelBox.valueChanged.connect(self._setLevel)
        self._blockBox.valueChanged.connect(self._setBlockSize)
        self._cBox.valueChanged.connect(self._setC)

    @QtCore.Slot(str)
    def _setMethod(self, method: str) -> None:
        self.videoFilter.method = method
        is_global = method == 'Global'
        is_adaptive = method.startswith('Adaptive')
        self._levelBox.setVisible(is_global)
        self._blockBox.setVisible(is_adaptive)
        self._cBox.setVisible(is_adaptive)

    @QtCore.Slot(object)
    def _setLevel(self, value: int) -> None:
        self.videoFilter.threshold = value
        with QtCore.QSignalBlocker(self._levelBox):
            self._levelBox.setValue(self.videoFilter.threshold)

    @QtCore.Slot(object)
    def _setBlockSize(self, value: int) -> None:
        self.videoFilter.block_size = value
        with QtCore.QSignalBlocker(self._blockBox):
            self._blockBox.setValue(self.videoFilter.block_size)

    @QtCore.Slot(object)
    def _setC(self, value: int) -> None:
        self.videoFilter.C = value


if __name__ == '__main__':  # pragma: no cover
    QThresholdFilter.example()
