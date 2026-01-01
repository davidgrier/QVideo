from pyqtgraph.Qt.QtWidgets import (QGroupBox, QWidget, QHBoxLayout)
import numpy as np


__all__ = ['VideoFilter', 'QVideoFilter']


class VideoFilter:

    '''Base class for video filters'''

    def __call__(self, data: np.ndarray) -> np.ndarray:
        self.add(data)
        return self.get()

    def add(self, data: np.ndarray) -> None:
        self.data = data

    def get(self) -> np.ndarray:
        return self.data


class QVideoFilter(QGroupBox):

    def __init__(self,
                 title: str,
                 parent: QWidget,
                 filter: VideoFilter) -> None:
        super().__init__(title, parent)
        self.filter = filter
        self._setupUi()

    def __call__(self, image: np.ndarray) -> np.ndarray:
        return self.filter(image) if self.isChecked() else image

    def _setupUi(self) -> None:
        self.setCheckable(True)
        self.setChecked(False)
        self.setFlat(True)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 5, 2, 5)

    def setFilter(self, filter: VideoFilter):
        self._filter = filter

    @classmethod
    def example(cls: 'QVideoFilter') -> None:
        import pyqtgraph as pg

        app = pg.mkQApp()
        widget = cls()
        widget.show()
        pg.exec()
