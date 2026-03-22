from QVideo.filters._MedianBase import _MedianBase
from QVideo.lib.types import Image
import numpy as np


__all__ = ['MoMedian']


class MoMedian(_MedianBase):

    '''Streaming median-of-medians background estimator.

    Computes a running pixel-wise median over ``3 ** order`` frames
    using a rolling two-frame buffer.  Unlike :class:`Median`, a new
    estimate is produced on *every* frame (not every third), at the
    cost of a slightly less accurate result for small ``order``.

    Parameters
    ----------
    order : int
        Recursion depth.  The estimate draws from ``3 ** order``
        frames.  Default: ``1`` (median of 3 frames).
    data : Image or None
        Optional seed frame used to pre-allocate internal buffers.
        If ``None`` the buffers are allocated on the first call to
        :meth:`add`.  Default: ``None``.

    Notes
    -----
    :class:`MoMedian` is a rolling variant of the remedian [R90]_: rather than
    waiting for a complete triplet, it uses the two most recently stored
    frames together with the current frame to produce a new estimate on
    every call.  This reduces latency at the cost of slight accuracy loss
    relative to the strict remedian.

    References
    ----------
    .. [R90] P.J. Rousseeuw and G.W. Bassett Jr., "The remedian: a robust
       averaging method for large data sets", *Journal of the American
       Statistical Association*, 85(409):97–104, 1990.
       `doi:10.1080/01621459.1990.10475311 <https://doi.org/10.1080/01621459.1990.10475311>`_
    '''

    def add(self, data: Image) -> None:
        '''Incorporate a new frame into the median estimate.

        Produces a new estimate on every call using a rolling
        two-frame buffer.

        Parameters
        ----------
        data : Image
            Input frame.  If the shape differs from the previously seen
            shape, the internal buffers are reallocated.
        '''
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
