from QVideo.lib.VideoFilter import VideoFilter
from QVideo.lib.types import Image
import numpy as np


__all__ = ['MoMedian']


class MoMedian(VideoFilter):

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
    '''

    def __init__(self,
                 order: int = 1,
                 data: Image | None = None) -> None:
        super().__init__()
        self._order = order
        self._clear()
        if data is not None:
            self._initialize(data)

    def _clear(self) -> None:
        '''Reset to uninitialized state, forgetting frame shape.

        Called on construction and when :attr:`order` changes.  Sets
        all internal buffers to ``None`` so that the next :meth:`add`
        triggers a fresh allocation via :meth:`_initialize`.
        '''
        self._index = 0
        self._next = None
        self.shape = None
        self._result = None

    def _initialize(self, data: Image) -> None:
        '''Allocate internal buffers for the given frame shape.

        Called on the first :meth:`add` after construction or after a
        frame-shape change.  Always requires a concrete frame so that
        buffer shape and dtype can be inferred.

        Parameters
        ----------
        data : Image
            Representative frame.
        '''
        self._index = 0
        self._next = None
        self.shape = data.shape
        self._result = data.copy()
        self._buffer = np.zeros((2, *self.shape), data.dtype)
        if self._order > 1:
            self._next = MoMedian(self._order - 1, data)

    def add(self, data: Image) -> None:
        '''Incorporate a new frame into the median estimate.

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

    def get(self) -> Image | None:
        '''Return the most recent median estimate.

        Returns
        -------
        Image or None
            Most recent estimate, or ``None`` if no frames have been
            added yet.
        '''
        return self._result

    @property
    def order(self) -> int:
        '''Recursion depth; contributes ``3 ** order`` frames.'''
        return self._order

    @order.setter
    def order(self, order: int) -> None:
        if order != self._order:
            self._order = order
            self._clear()

    def reset(self) -> None:
        '''Clear all buffers and restart the estimator.

        Fills the result and frame buffers with zeros and resets the
        frame index.  Does not reallocate memory.
        '''
        self._result.fill(0)
        self._buffer.fill(0)
        self._index = 0
        if self._next is not None:
            self._next.reset()
