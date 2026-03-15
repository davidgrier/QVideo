from QVideo.filters.Median import Median
import numpy as np
import numba as nb
from time import perf_counter


class FastMedian(Median):

    @staticmethod
    @nb.njit("void(u1[:], u1[:], u1[:], u1[:])", fastmath=True, parallel=True)
    def median(a: np.ndarray,
               b: np.ndarray,
               c: np.ndarray,
               out: np.ndarray) -> None:
        for n in range(len(a)):
            out[n] = max(min(a[n], b[n]), min(max(a[n], b[n]), c[n]))

    def add(self, data: np.ndarray) -> None:
        '''Incorporates new data into the median estimate'''
        if data.shape != self.shape:
            self._initialize(data)
        if self._next is not None:
            self._next.add(data)
            if self._next.ready():
                data = self._next.get()
            else:
                return
        if self._index == 2:
            start = perf_counter()
            a = self._buffer[0].flatten()
            b = self._buffer[1].flatten()
            self.median(a, b, data.flatten(), self._result.flatten())
            print(perf_counter()-start)
#            self._result = np.maximum(np.minimum(a, b),
#                                      np.minimum(np.maximum(a, b), data))
            self._index = 0
            self._ready = True
        self._buffer[self._index] = data
        self._index += 1
