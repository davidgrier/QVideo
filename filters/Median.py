from QVideo.filters._MedianBase import _MedianBase
from QVideo.lib.types import Image
import numpy as np


__all__ = ['Median']


class Median(_MedianBase):

    '''Fast median-of-medians background estimator.

    Computes a running pixel-wise median over ``3 ** order`` frames
    using a recursive median-of-three algorithm that requires only two
    frame buffers per level.

    Parameters
    ----------
    order : int
        Recursion depth.  The median is computed over ``3 ** order``
        frames.  Default: ``1`` (median of 3 frames).
    data : Image or None
        Optional seed frame used to pre-allocate internal buffers.
        If ``None`` the buffers are allocated on the first call to
        :meth:`add`.  Default: ``None``.

    Notes
    -----
    Results are only available once :meth:`ready` returns ``True``,
    which requires at least ``3 ** order`` frames to have been added.
    Before that point :meth:`get` returns whatever seed data was
    provided (or ``None``).

    The :meth:`reset` method clears all buffers and resets the ready
    flag so that the estimator starts fresh without reallocating memory.

    References
    ----------
    .. [1] P.J. Rousseeuw and G.W. Bassett Jr., "The remedian: a robust
       averaging method for large data sets", *Journal of the American
       Statistical Association*, 85(409):97–104, 1990.
       :doi:`10.1080/01621459.1990.10475311`
    '''

    def add(self, data: Image) -> None:
        '''Incorporate a new frame into the median estimate.

        Resets the ready flag at the start of each call so that
        :meth:`ready` reflects only whether *this* call produced a new
        estimate.

        Parameters
        ----------
        data : Image
            Input frame.  If the shape differs from the previously seen
            shape, the internal buffers are reallocated.
        '''
        self._ready = False
        if data.shape != self.shape:
            self._initialize(data)
        if self._next is not None:
            self._next.add(data)
            if self._next.ready():
                data = self._next.get()
            else:
                return
        if self._index == 2:
            a = self._buffer[0]
            b = self._buffer[1]
            self._result = np.maximum(np.minimum(a, b),
                                      np.minimum(np.maximum(a, b), data))
            self._index = 0
            self._ready = True
        self._buffer[self._index] = data
        self._index += 1

    def ready(self) -> bool:
        '''Return ``True`` if the most recent :meth:`add` produced a new estimate.

        The flag is reset at the start of each :meth:`add` call and set
        again only if that call completes a new median computation.
        Calling :meth:`get` does not affect this flag.

        Returns
        -------
        bool
            ``True`` if the last :meth:`add` yielded a fresh estimate.
        '''
        return self._ready
