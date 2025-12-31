from pyqtgraph.Qt.QtCore import QObject
from QVideo.lib.VideoFilter import VideoFilter
import numpy as np


class QFilterBank(QObject):

    def __init__(self) -> None:
        super().__init__()
        self.filters = []

    def __call__(self, data: np.ndarray) -> None:
        for filter in self.filters:
            data = filter(data)
        return data

    def register(self, filter: VideoFilter) -> None:
        self.filters.append(filter)

    def deregister(self, filter: VideoFilter) -> None:
        self.filters.remove(filter)
