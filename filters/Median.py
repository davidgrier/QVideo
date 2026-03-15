from QVideo.lib.VideoFilter import VideoFilter
from QVideo.lib.types import Image


__all__ = ['Median']


class Median(VideoFilter):

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
    '''

    def __init__(self,
                 order: int = 1,
                 data: Image | None = None) -> None:
        super().__init__()
        self._order = order
        self._initialize(data)

    def _initialize(self, data: Image | None = None) -> None:
        '''Allocate internal buffers for the given frame shape.

        Parameters
        ----------
        data : Image or None
            Seed frame.  If ``None`` all buffers are set to ``None``
            and initialisation is deferred to the first :meth:`add`.
        '''
        import numpy as np
        self._index = 0
        self._ready = False
        if data is None:
            self.shape = None
            self._result = None
            return
        self.shape = data.shape
        self._result = data.copy()
        self._buffer = np.ones((2, *self.shape), data.dtype)
        self._next = Median(self._order - 1, data) if self._order > 1 else None

    def add(self, data: Image) -> None:
        '''Incorporate a new frame into the median estimate.

        Parameters
        ----------
        data : Image
            Input frame.  If the shape differs from the previously seen
            shape, the internal buffers are reallocated.
        '''
        import numpy as np
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

    def get(self) -> Image | None:
        '''Return the most recent median estimate.

        Returns
        -------
        Image or None
            Most recent estimate, or ``None`` if no frames have been
            added yet.  Calling ``get`` resets the ready flag.
        '''
        self._ready = False
        return self._result

    def ready(self) -> bool:
        '''Return ``True`` if a new estimate is available.

        Returns
        -------
        bool
            ``True`` after every ``3 ** order`` frames until :meth:`get`
            is called.
        '''
        return self._ready

    @property
    def order(self) -> int:
        '''Recursion depth; contributes ``3 ** order`` frames.'''
        return self._order

    @order.setter
    def order(self, order: int) -> None:
        if order != self._order:
            self._order = order
            self._initialize()

    def reset(self) -> None:
        '''Clear all buffers and restart the estimator.

        Fills the result and frame buffers with zeros and resets the
        frame counter and ready flag.  Does not reallocate memory.
        '''
        if self._result is not None:
            self._result.fill(0)
            self._buffer.fill(0)
        self._index = 0
        self._ready = False
        if self._next is not None:
            self._next.reset()
