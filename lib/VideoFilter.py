from abc import (ABC, abstractmethod)
import numpy as np


class VideoFilter(ABC):

    '''Base class for video filters'''

    def __call__(self, data: np.ndarray) -> np.ndarray:
        self.add(data)
        return self.get()

    @abstractmethod
    def add(self, data: np.ndarray) -> None:
        self.data = data

    @abstractmethod
    def get(self) -> np.ndarray:
        return self.data
