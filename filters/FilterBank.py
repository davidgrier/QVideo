from PyQt5.QtCore import QObject
from QVideo.lib.VideoFilter import VideoFilter
import numpy as np


class FilterBank(QObject):

    def __init__(self, interval: float = 0.03) -> None:
        super().__init__()
        self.filters = []
        self.interval = interval

    def __call__(self, data: np.ndarray) -> None:
        for filter in self.filters:
            data = filter(data)
        return data

    def register(self, filter: VideoFilter) -> None:
        self.filters.append(filter)

    def deregister(self, filter: VideoFilter) -> None:
        self.filters.remove(filter)
