from pyqtgraph.Qt.QtWidgets import (QWidget, QLabel)
from pyqtgraph import SpinBox
from pyqtgraph.Qt.QtCore import pyqtSlot
from QVideo.lib.VideoFilter import (QVideoFilter, VideoFilter)
import numpy as np
import cv2


__all__ = ['QEdgeFilter', 'EdgeFilter']


class QEdgeFilter(QVideoFilter):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__('Canny Edge Detection', parent, EdgeFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self.layout.addWidget(QLabel('low'))
        low = SpinBox(self, value=self.filter.low, int=True)
        low.setMinimum(1)
        low.valueChanged.connect(self.setLow)
        self.layout.addWidget(low)
        self.layout.addWidget(QLabel('high'))
        high = SpinBox(self, value=self.filter.high, int=True)
        high.setMinimum(2)
        high.valueChanged.connect(self.setHigh)
        self.layout.addWidget(high)

    @pyqtSlot(object)
    def setLow(self, low: int) -> None:
        self.filter.low = low

    @pyqtSlot(object)
    def setHigh(self, high: int) -> None:
        self.filter.high = high


class EdgeFilter(VideoFilter):

    def __init__(self, low: int = 50, high: int = 150) -> None:
        super().__init__()
        self.low = low
        self.high = high

    def add(self, image: np.ndarray) -> None:
        if image.ndim == 3:
            self.data = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            self.data = image

    def get(self) -> np.ndarray:
        return cv2.Canny(self.data, self.low, self.high)


if __name__ == '__main__':
    QEdgeFilter.example()
