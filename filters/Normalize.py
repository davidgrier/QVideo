from QVideo.filters.Median import Median
import numpy as np


class Normalize(Median):

    '''Normalize image by running-median background estimate'''

    def __init__(self, *args, scale=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.scale = scale

    def add(self, data: np.ndarray) -> None:
        super().add(data)
        self._fg = data.astype(float)

    def get(self) -> np.ndarray:
        result = self._fg / super().get().astype(float)
        return (100. * result).astype(np.uint8) if self.scale else result
