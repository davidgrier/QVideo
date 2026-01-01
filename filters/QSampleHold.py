from pyqtgraph.Qt.QtWidgets import (QWidget, QPushButton)
from pyqtgraph.Qt.QtCore import pyqtSlot
from QVideo.lib.VideoFilter import QVideoFilter
from QVideo.filters.Normalize import Normalize
import numpy as np


class QSampleHold(QVideoFilter):

    '''GUI widget for SampleHold filter
    '''

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__('Sample and Hold', parent, SampleHold())

    def _setupUi(self) -> None:
        super()._setupUi()
        resetButton = QPushButton('Reset', self)
        self.layout.addWidget(resetButton)
        resetButton.clicked.connect(self.reset)

    @pyqtSlot(bool)
    def reset(self, checked) -> None:
        self.filter.reset()


class SampleHold(Normalize):

    '''Normalize image by a previously sampled background estimate

    Inherits
    --------
    QVideo.filters.Normalize

    Methods
    -------
    reset(): None
        Recompute the background estimate
    '''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.reset()

    def reset(self) -> None:
        self.count = 3**self.order

    def add(self, data: np.ndarray) -> None:
        if data.shape != self.shape:
            self.reset()
        if self.count > 0:
            super().add(data)
            self.count -= 1
        else:
            self._fg = data - self.darkcount


if __name__ == '__main__':
    QSampleHold.example()
