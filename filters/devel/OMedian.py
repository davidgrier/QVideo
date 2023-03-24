import numpy as np
from typing import Optional


class OMedian(object):

    def __init__(self,
                 order: int = 1,
                 data: Optional[np.ndarray] = None) -> None:
        self._order = order
        self._initialize(data)

    def __call__(self, data: np.ndarray) -> np.ndarray:
        self.add(data)
        return self.get()

    def _initialize(self, data: np.ndarray) -> None:
        self._index = 0
        self._ready = False
        if data is None:
            self.shape = None
            self._result = None
            return
        self.shape = data.shape
        self.dtype = data.dtype
        self._result = data
        self._buffer = np.zeros((3, *self.shape), self.dtype)
        if self._order > 1:
            self._next = Median(self._order-1, data)
        else:
            self._next = None

    def ready(self) -> bool:
        return self._ready

    def add(self, data: np.ndarray) -> None:
        if data.shape != self.shape:
            self._initialize(data)
        if self._next is not None:
            self._next.add(data)
            if self._next.ready():
                data = self._next.get()
            else:
                return
        self._buffer[self._index] = data
        self._index += 1
        if self._index == 3:
            self._result = np.median(self._buffer, axis=0)
            self._ready = True
            self._index = 0

    def get(self) -> Optional[np.ndarray]:
        self._ready = False
        return self._result.astype(self.dtype)

    def reset(self) -> None:
        self._result.fill(self.dtype(0))
        self._buffer.fill(self.dtype(0))
        self._index = 0
        if self._next is not None:
            self._next.reset()
