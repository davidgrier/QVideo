from QVideo.lib.VideoFilter import VideoFilter
import numpy as np
from typing import Optional


class MoMedian(VideoFilter):

    '''Median of medians filter'''

    def __init__(self,
                 order: int = 1,
                 data: Optional[np.ndarray] = None) -> None:
        self._order = order
        self._initialize(data)

    def _initialize(self, data: Optional[np.ndarray] = None) -> None:
        self._index = 0
        if data is None:
            self.shape = None
            self._result = None
            return
        self.shape = data.shape
        self._result = data
        self._buffer = np.zeros((2, *self.shape), data.dtype)
        if self._order > 1:
            self._next = MoMedian(self._order-1, data)
        else:
            self._next = None

    def add(self, data: np.ndarray) -> None:
        '''Incorporates new data into the median estimate'''
        if data.shape != self.shape:
            self._initialize(data)
        if self._order > 1:
            data = self._next(data)
        a = self._buffer[0]
        b = self._buffer[1]
        self._result = np.maximum(np.minimum(a, b),
                                  np.minimum(np.maximum(a, b), data))
        self._buffer[self._index] = data
        self._index = (self._index + 1) % 2

    def get(self) -> Optional[np.ndarray]:
        '''Returns the most recent median estimate'''
        return self._result

    @property
    def order(self) -> int:
        '''Number of contributing images = 3^order'''
        return self._order

    @order.setter
    def order(self, order: int) -> None:
        if order != self._order:
            self._order = order
            self._initialize()

    def reset(self) -> None:
        self._result.fill(self.dtype(0))
        self._buffer.fill(self.dtype(0))
        self._index = 0
        if self._next is not None:
            self._next.reset()