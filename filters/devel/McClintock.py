import numpy as np
from typing import Optional


class McClintock(object):

    '''https://stackoverflow.com/a/7485717'''

    def __init__(self,
                 data: Optional[np.ndarray] = None,
                 eta: float = 0.1) -> None:
        self.eta = eta
        self.median = None
        if data is not None:
            self.add(data)

    def __call__(self, data:np.ndarray) -> np.ndarray:
        self.add(data)
        return self.get()

    def add(self, data: np.ndarray) -> None:
        if self.median is None:
            self.dtype = data.dtype
            self.median = data.astype(float)
        else:
            delta = np.sign(data.astype(float) - self.median)
            self.median += self.eta * delta

    def get(self) -> np.ndarray:
        return self.median.astype(self.dtype)
