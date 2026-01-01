from pyqtgraph.Qt.QtWidgets import (QWidget, QLabel)
from pyqtgraph import SpinBox
from pyqtgraph.Qt.QtCore import (pyqtSlot, pyqtProperty)
from QVideo.lib.VideoFilter import (QVideoFilter, VideoFilter)
import numpy as np
import cv2


__all__ = ['BlurFilter', 'QBlurFilter']


class QBlurFilter(QVideoFilter):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__('Gaussian Blur', parent, BlurFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self.layout.addWidget(QLabel('width'))
        spinbox = SpinBox(self, value=self.filter.width, step=2, int=True)
        self.layout.addWidget(spinbox)
        spinbox.setMinimum(1)
        spinbox.valueChanged.connect(self.setWidth)

    @pyqtSlot(object)
    def setWidth(self, width: int) -> None:
        self.filter.width = width


class BlurFilter(VideoFilter):

    '''Performs a Gaussian blur

    Properties
    ----------
    width : int
        extent of Gaussian blur
    '''

    def __init__(self, width: int = 15) -> None:
        super().__init__()
        self.width = width

    def add(self, image: np.ndarray) -> None:
        self.data = image

    def get(self) -> np.ndarray:
        return cv2.GaussianBlur(self.data, 2*(self.width,), 0)

    @pyqtProperty(int)
    def width(self):
        return self._width

    @width.setter
    def width(self, width: int):
        self._width = int(width + (1 - width % 2))


if __name__ == '__main__':
    QBlurFilter.example()
