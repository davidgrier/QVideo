'''Smoothing filter with selectable method and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image
import cv2


__all__ = ['SmoothingFilter', 'QSmoothingFilter']

class SmoothingFilter(AsyncVideoFilter):

    '''Smoothing filter supporting box, Gaussian, and median blur.

    Parameters
    ----------
    width : int
        Kernel width in pixels.  Must be odd and at least 1; even values
        are rounded up to the next odd integer.  Default: ``15``.
    method : str
        Smoothing method: ``'box'``, ``'gaussian'``, or ``'median'``.
        Default: ``'gaussian'``.

    Notes
    -----
    OpenCV requires an odd, positive kernel size for ``GaussianBlur``
    and ``medianBlur``.  ``blur`` (box filter) accepts any positive
    size, but the :attr:`width` setter enforces odd values uniformly
    across all methods.

    For Gaussian blur, ``sigma`` is set to 0, which instructs OpenCV
    to derive it from the kernel size.
    '''

    METHODS = ('box', 'gaussian', 'median')

    def __init__(self, width: int = 15, method: str = 'gaussian') -> None:
        super().__init__()
        self.width = width
        self.method = method

    @property
    def width(self) -> int:
        '''Kernel width [pixels], always odd and at least 1.'''
        return self._width

    @width.setter
    def width(self, width: int) -> None:
        width = max(1, int(width))
        self._width = width - (width % 2) + 1

    @property
    def method(self) -> str:
        '''Smoothing method: ``'box'``, ``'gaussian'``, or ``'median'``.'''
        return self._method

    @method.setter
    def method(self, method: str) -> None:
        if method not in self.METHODS:
            raise ValueError(f'method must be one of {self.METHODS}')
        self._method = method

    def to_code(self) -> 'FilterCode':
        from QVideo.lib.QVideoFilter import FilterCode
        k = self._width
        if self._method == 'box':
            return FilterCode(
                imports=frozenset({'import cv2'}),
                lines=[f'image = cv2.blur(image, ({k}, {k}))'],
                comment=f'box smoothing, k={k}',
            )
        if self._method == 'median':
            return FilterCode(
                imports=frozenset({'import cv2'}),
                lines=[f'image = cv2.medianBlur(image, {k})'],
                comment=f'median smoothing, k={k}',
            )
        return FilterCode(
            imports=frozenset({'import cv2'}),
            lines=[f'image = cv2.GaussianBlur(image, ({k}, {k}), 0)'],
            comment=f'Gaussian smoothing, k={k}',
        )

    def process(self, image: Image) -> Image:
        '''Return the smoothed frame.

        Called in the background thread.

        Returns
        -------
        Image
            Smoothed version of *image*.
        '''
        if self._method == 'box':
            return cv2.blur(image, (self._width, self._width))
        if self._method == 'median':
            return cv2.medianBlur(image, self._width)
        return cv2.GaussianBlur(image, (self._width, self._width), 0)


class QSmoothingFilter(QVideoFilter):

    '''Widget for :class:`SmoothingFilter` with method selector and width spinbox.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Smoothing'
    display_category = 'Preprocessing'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Smoothing', SmoothingFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._methodBox = QtWidgets.QComboBox()
        self._methodBox.addItems(['Box', 'Gaussian', 'Median'])
        self._methodBox.setCurrentText(self.filter.method.capitalize())
        self._layout.addWidget(self._methodBox)
        self._spinbox = SpinBox(self, prefix='width: ',
                                value=self.filter.width,
                                step=1, int=True)
        self._spinbox.setMinimum(3)
        self._layout.addWidget(self._spinbox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._methodBox.currentTextChanged.connect(self._setMethod)
        self._spinbox.valueChanged.connect(self._setWidth)

    @QtCore.Slot(str)
    def _setMethod(self, text: str) -> None:
        self.filter.method = text.lower()

    @QtCore.Slot(object)
    def _setWidth(self, width: int) -> None:
        self.filter.width = width
        with QtCore.QSignalBlocker(self._spinbox):
            self._spinbox.setValue(self.filter.width)


if __name__ == '__main__':  # pragma: no cover
    QSmoothingFilter.example()
