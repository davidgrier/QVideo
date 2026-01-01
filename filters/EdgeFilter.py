from pyqtgraph.Qt.QtWidgets import (
    QWidget, QGroupBox, QHBoxLayout, QCheckBox)
from pyqtgraph.Qt.QtCore import pyqtSlot
from QVideo.lib.VideoFilter import VideoFilter
import numpy as np
import cv2


class QEdgeFilter(QGroupBox):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__('Edge Detection', parent)
        self.filter = EdgeFilter()
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

    @pyqtSlot(int)
    def enable(self, state: int) -> None:
        self._enabled = bool(state)


class EdgeFilter(VideoFilter):

    def add(self, image: np.ndarray) -> None:
        if image.ndim == 3:
            self.data = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            self.data = image

    def get(self) -> np.ndarray:
        return cv2.Canny(self.data, 50, 150)


def example() -> None:
    import pyqtgraph as pg

    app = pg.mkQApp()
    widget = QEdgeFilter()
    widget.show()
    pg.exec()


if __name__ == '__main__':
    example()
