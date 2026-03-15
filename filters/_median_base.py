from QVideo.lib.VideoFilter import VideoFilter
from QVideo.lib.types import Image
import numpy as np


class _MedianBase(VideoFilter):

    '''Shared base for median-of-medians background estimators.

    Provides buffer management, the ``order`` property, and ``reset``.
    Subclasses implement :meth:`add` with their own update cadence.

    Parameters
    ----------
    order : int
        Recursion depth.  The estimator draws from ``3 ** order``
        frames.  Default: ``1``.
    data : Image or None
        Optional seed frame for pre-allocating buffers.  Default: ``None``.
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

        Called on construction and when :attr:`order` changes.
        '''
        self._index = 0
        self._ready = False
        self._next = None
        self.shape = None
        self._result = None

    def _initialize(self, data: Image) -> None:
        '''Allocate internal buffers for the given frame shape.

        Uses ``type(self)`` for the recursive sub-estimator so that
        :class:`Median` chains :class:`Median` instances and
        :class:`MoMedian` chains :class:`MoMedian` instances without
        any subclass override.

        Parameters
        ----------
        data : Image
            Representative frame; determines buffer shape and dtype.
        '''
        self._index = 0
        self._ready = False
        self._next = None
        self.shape = data.shape
        self._result = data.copy()
        self._buffer = np.zeros((2, *self.shape), data.dtype)
        if self._order > 1:
            self._next = type(self)(self._order - 1, data)

    def get(self) -> Image | None:
        '''Return the most recent estimate.

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
        frame counter and ready flag.  Does not reallocate memory.
        '''
        self._result.fill(0)
        self._buffer.fill(0)
        self._index = 0
        self._ready = False
        if self._next is not None:
            self._next.reset()
