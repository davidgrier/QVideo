from pyqtgraph.Qt.QtWidgets import (QGroupBox, QHBoxLayout,
                                    QCheckBox, QPushButton)
from pyqtgraph.Qt.QtCore import pyqtSlot
from QVideo.filters.Normalize import Normalize
import numpy as np


class QSampleHold(QGroupBox):

    '''GUI widget for SampleHold filter
    '''

    def __init__(self, parent: QGroupBox | None = None) -> None:
        super().__init__('Sample and Hold', parent)
        self.filter = SampleHold()
        self._enabled = False
        self._setupUi()

    def __call__(self, image: np.ndarray) -> np.ndarray:
        return self.filter(image) if self._enabled else image

    def _setupUi(self) -> None:
        layout = QHBoxLayout(self)
        enabledBox = QCheckBox('Enabled', self)
        layout.addWidget(enabledBox)
        resetButton = QPushButton('Reset', self)
        layout.addWidget(resetButton)
        enabledBox.stateChanged.connect(self.enable)
        resetButton.clicked.connect(self.reset)
        enabledBox.setChecked(self._enabled)

    @pyqtSlot(int)
    def enable(self, state: int) -> None:
        self._enabled = bool(state)

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
