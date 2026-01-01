from pyqtgraph.Qt.QtWidgets import (QGroupBox, QWidget, QVBoxLayout)
from QVideo.lib.VideoFilter import QVideoFilter
import numpy as np
import QVideo.filters
from pathlib import Path
from importlib import import_module


class QFilterBank(QGroupBox):

    def __init__(self, parent: QWidget) -> None:
        super().__init__('Display Filters', parent)
        self.filters = []
        self._setupUi()

    def _setupUi(self) -> None:
        self.layout = QVBoxLayout(self)

    def __call__(self, data: np.ndarray) -> np.ndarray:
        for filter in self.filters:
            data = filter(data)
        return data

    def register(self, filter: QVideoFilter) -> None:
        self.filters.append(filter)
        self.layout.addWidget(filter)

    def deregister(self, filter: QVideoFilter) -> None:
        self.filters.remove(filter)
        self.layout.removeWidget(filter)

    def registerByName(self, filtername: str) -> None:
        modulename = f'QVideo.filters.{filtername}'
        module = import_module(modulename)
        if hasattr(module, filtername):
            filter = getattr(module, filtername)()
            self.register(filter)
        else:
            print(modulename)
