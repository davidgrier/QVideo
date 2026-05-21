from QVideo.lib.QVideoFilter import VideoFilter
from QVideo.lib.videotypes import Image
import numpy as np


class _MedianBase(VideoFilter):

    '''Shared base for Remedian background estimators.

    Provides buffer management, the ``order`` property, and ``reset``.
    Subclasses implement :meth:`add` with their own update cadence.

    Class Attributes
    ----------------
    _sub_type : type or None
        Sub-estimator class used when building recursive chains.
        ``None`` (default) means use ``type(self)``, which is correct
        for pure estimator chains (``Median`` → ``Median``,
        ``MoMedian`` → ``MoMedian``).  Override in subclasses whose
        ``add()`` behaviour must not propagate into sub-estimators
        (e.g. :class:`~QVideo.filters.samplehold.SampleHold` uses
        ``Median`` so the sub-estimator never enters hold mode).

    Parameters
    ----------
    order : int
        Recursion depth.  The estimator draws from ``3 ** order``
        frames.  Default: ``1``.
    data : Image or None
        Optional seed frame for pre-allocating buffers.  Default: ``None``.

    References
    ----------
    .. [1] P.J. Rousseeuw and G.W. Bassett Jr., "The remedian: a robust
       averaging method for large data sets", *Journal of the American
       Statistical Association*, 85(409):97–104, 1990.
       :doi:`10.1080/01621459.1990.10475311`
    '''

    _sub_type: 'type[_MedianBase] | None' = None

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
        self._buffer = np.array([data, data])
        if self._order > 1:
            cls = self._sub_type if self._sub_type is not None else type(self)
            self._next = cls(self._order - 1, data)

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
        '''Clear accumulated state and restart the estimator.

        Clears the stored shape so that the next :meth:`add` call
        triggers :meth:`_initialize`, re-seeding the buffers from the
        incoming frame just as on first use.
        '''
        self.shape = None
        self._result = None
        self._index = 0
        self._ready = False
        if self._next is not None:
            self._next.reset()
