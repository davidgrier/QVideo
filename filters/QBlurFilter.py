from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.types import Image
import cv2


__all__ = ['BlurFilter', 'QBlurFilter']


class BlurFilter(VideoFilter):

    '''Gaussian blur filter.

    Parameters
    ----------
    width : int
        Kernel width in pixels.  Must be odd and at least 1; even values
        are rounded up to the next odd integer.  Default: ``15``.

    Notes
    -----
    OpenCV's ``GaussianBlur`` requires an odd, positive kernel size.
    The :attr:`width` setter enforces this automatically.

    ``sigma`` is set to 0, which instructs OpenCV to derive it from the
    kernel size.  Subclasses that need explicit sigma control should
    override :meth:`get`.
    '''

    def __init__(self, width: int = 15) -> None:
        super().__init__()
        self.width = width

    @property
    def width(self) -> int:
        '''Kernel width [pixels], always odd and at least 1.'''
        return self._width

    @width.setter
    def width(self, width: int) -> None:
        width = max(1, int(width))
        self._width = width - (width % 2) + 1

    def get(self) -> Image | None:
        '''Return the Gaussian-blurred frame.

        Returns
        -------
        Image or None
            Blurred version of the most recently added frame, or
            ``None`` if no frame has been added yet.
        '''
        if self.data is None:
            return None
        return cv2.GaussianBlur(self.data, (self.width, self.width), 0)


class QBlurFilter(QVideoFilter):

    '''Widget for :class:`BlurFilter` with a kernel-width spinbox.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Gaussian Blur', BlurFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._layout.addWidget(QtWidgets.QLabel('width'))
        self._spinbox = SpinBox(self, value=self.filter.width,
                                step=1, int=True)
        self._spinbox.setMinimum(3)
        self._spinbox.valueChanged.connect(self.setWidth)
        self._layout.addWidget(self._spinbox)

    @QtCore.pyqtSlot(object)
    def setWidth(self, width: int) -> None:
        '''Set the blur kernel width.

        Passes *width* to :class:`BlurFilter`, which enforces odd values,
        then snaps the spinbox display to the corrected value.

        Parameters
        ----------
        width : int
            New kernel width.  Even values are rounded up to the next
            odd integer.
        '''
        self.filter.width = width
        self._spinbox.blockSignals(True)
        self._spinbox.setValue(self.filter.width)
        self._spinbox.blockSignals(False)


if __name__ == '__main__':  # pragma: no cover
    QBlurFilter.example()
