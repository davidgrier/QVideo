from QVideo.filters.Normalize import Normalize
import numpy as np


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
