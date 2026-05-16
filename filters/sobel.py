'''Sobel gradient edge-detection filter and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np
import cv2

__all__ = ['SobelFilter', 'QSobelFilter']


class SobelFilter(VideoFilter):

    '''Sobel edge detector with horizontal, vertical, and magnitude modes.

    Converts each frame to grayscale, then applies the Sobel operator.

    - **Horizontal**: first-order x-derivative (∂/∂x), converted to uint8.
    - **Vertical**: first-order y-derivative (∂/∂y), converted to uint8.
    - **Magnitude**: Euclidean magnitude of the (∂/∂x, ∂/∂y) gradient,
      clipped to [0, 255].

    Parameters
    ----------
    direction : str
        One of ``'Horizontal'``, ``'Vertical'``, ``'Magnitude'``.
        Default: ``'Magnitude'``.
    ksize : int
        Sobel kernel size [pixels].  Must be odd and in {1, 3, 5, 7}.
        Default: ``3``.
    '''

    DIRECTIONS = ('Horizontal', 'Vertical', 'Magnitude')

    def __init__(self,
                 direction: str = 'Magnitude',
                 ksize: int = 3) -> None:
        super().__init__()
        self.direction = direction
        self.ksize = ksize

    @property
    def direction(self) -> str:
        '''Gradient mode; one of :attr:`DIRECTIONS`.'''
        return self._direction

    @direction.setter
    def direction(self, value: str) -> None:
        if value not in self.DIRECTIONS:
            raise ValueError(f'unknown direction: {value!r}')
        self._direction = value

    @property
    def ksize(self) -> int:
        '''Sobel kernel size [pixels], always odd and in {1, 3, 5, 7}.'''
        return self._ksize

    @ksize.setter
    def ksize(self, value: int) -> None:
        value = max(1, min(7, int(value)))
        self._ksize = value + (1 - value % 2)

    def to_code(self) -> 'FilterCode':
        from QVideo.lib.QVideoFilter import FilterCode
        _GRAY = [
            'if image.ndim == 3:',
            '    image = image.mean(axis=2).astype(np.uint8)',
        ]
        imports = frozenset({'import cv2', 'import numpy as np'})
        k = self._ksize
        if self._direction == 'Horizontal':
            return FilterCode(
                imports=imports,
                lines=_GRAY + [
                    f'image = cv2.convertScaleAbs(cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize={k}))',
                ],
                comment=f'Sobel horizontal, k={k}',
            )
        if self._direction == 'Vertical':
            return FilterCode(
                imports=imports,
                lines=_GRAY + [
                    f'image = cv2.convertScaleAbs(cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize={k}))',
                ],
                comment=f'Sobel vertical, k={k}',
            )
        return FilterCode(
            imports=imports,
            lines=_GRAY + [
                f'_gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize={k})',
                f'_gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize={k})',
                'image = np.clip(np.hypot(_gx, _gy), 0, 255).astype(np.uint8)',
            ],
            comment=f'Sobel magnitude, k={k}',
        )

    def get(self) -> Image | None:
        '''Return the Sobel edge map of the stored frame.

        Returns
        -------
        Image or None
            uint8 edge map, or ``None`` if no frame has been added.
        '''
        if self.data is None:
            return None
        gray = (self.data.mean(axis=2).astype(np.uint8)
                if self.data.ndim == 3 else self.data)
        if self._direction == 'Horizontal':
            result = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=self._ksize)
            return cv2.convertScaleAbs(result)
        elif self._direction == 'Vertical':
            result = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=self._ksize)
            return cv2.convertScaleAbs(result)
        else:
            gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=self._ksize)
            gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=self._ksize)
            return np.clip(np.hypot(gx, gy), 0, 255).astype(np.uint8)


class QSobelFilter(QVideoFilter):

    display_name = 'Sobel'
    display_category = 'Edge Detection'

    '''Widget for :class:`SobelFilter` with direction selector and kernel
    size spinbox.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Sobel Edge Detection', SobelFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._dirBox = QtWidgets.QComboBox()
        self._dirBox.addItems(SobelFilter.DIRECTIONS)
        self._dirBox.setCurrentText(self.filter.direction)
        self._layout.addWidget(self._dirBox)
        self._ksizeBox = SpinBox(value=self.filter.ksize,
                                 bounds=(1, 7), step=2, int=True,
                                 prefix='k ')
        self._layout.addWidget(self._ksizeBox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._dirBox.currentTextChanged.connect(self._setDirection)
        self._ksizeBox.valueChanged.connect(self._setKsize)

    @QtCore.Slot(str)
    def _setDirection(self, direction: str) -> None:
        self.filter.direction = direction

    @QtCore.Slot(object)
    def _setKsize(self, value: int) -> None:
        self.filter.ksize = value
        with QtCore.QSignalBlocker(self._ksizeBox):
            self._ksizeBox.setValue(self.filter.ksize)


if __name__ == '__main__':  # pragma: no cover
    QSobelFilter.example()
