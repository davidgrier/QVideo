from pyqtgraph.Qt.QtWidgets import (
    QWidget, QGroupBox, QHBoxLayout, QCheckBox)
from pyqtgraph import SpinBox
from pyqtgraph.Qt.QtCore import (pyqtSlot, pyqtProperty)
from QVideo.lib.VideoFilter import VideoFilter
import numpy as np
import cv2


__all__ = ['BlurFilter', 'QBlurFilter']


class QBlurFilter(QGroupBox):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__('Gaussian Blur', parent)
        self.filter = BlurFilter()
        self._enabled = False
        self._setupUi()

    def __call__(self, image: np.ndarray) -> np.ndarray:
        return self.filter(image) if self._enabled else image

    def _setupUi(self) -> None:
        layout = QHBoxLayout(self)
        enabledBox = QCheckBox('Enabled', self)
        layout.addWidget(enabledBox)
        enabledBox.stateChanged.connect(self.enable)
        enabledBox.setChecked(self._enabled)
        spinbox = SpinBox(self, value=self.filter.width, step=2, int=True)
        layout.addWidget(spinbox)
        spinbox.setMinimum(1)
        spinbox.valueChanged.connect(self.setWidth)

    @pyqtSlot(int)
    def enable(self, state: int) -> None:
        self._enabled = bool(state)

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


def example() -> None:
    import pyqtgraph as pg

    app = pg.mkQApp()
    widget = QBlurFilter()
    widget.show()
    pg.exec()


if __name__ == '__main__':
    example()
