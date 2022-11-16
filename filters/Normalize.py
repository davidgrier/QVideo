from QVideo.filters.Median import Median
import numpy as np


class Normalize(Median):

    '''Normalize image by running-median background estimate'''

    def add(self, data: np.ndarray) -> None:
        super().add(data)
        self._fg = data.astype(float)

    def get(self) -> np.ndarray:
        bg = super().get().astype(float)
        return (100 * self._fg / bg).astype(np.uint8)
