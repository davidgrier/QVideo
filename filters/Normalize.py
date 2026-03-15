from QVideo.filters.Median import Median
from QVideo.filters.MoMedian import MoMedian
from QVideo.lib.types import Image
import numpy as np


__all__ = ['Normalize', 'SmoothNormalize']


class _NormalizeMixin:

    '''Mixin that adds background normalization to a median estimator.

    Intended to be combined with :class:`~QVideo.filters.Median.Median`
    or :class:`~QVideo.filters.MoMedian.MoMedian` via multiple
    inheritance.  The median estimator accumulates frames to build a
    background model; this mixin divides new frames by that background.

    Parameters
    ----------
    *args :
        Positional arguments forwarded to the median base class.
    scale : bool
        If ``True`` the normalized result is multiplied by *mean* and
        cast to ``uint8``.  If ``False`` the raw floating-point ratio
        is returned.  Default: ``True``.
    mean : float
        Target mean value used when *scale* is ``True``.
        Default: ``100.0``.
    darkcount : int
        Constant offset subtracted from each frame before processing,
        representing the camera dark-count level.  Default: ``0``.
    **kwargs :
        Keyword arguments forwarded to the median base class.

    Notes
    -----
    The input frame is never modified in place; a copy is made before
    the dark-count is subtracted.

    Where the background estimate is zero the normalized output is also
    set to zero to avoid undefined values.
    '''

    def __init__(self, *args,
                 scale: bool = True,
                 mean: float = 100.,
                 darkcount: int = 0,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.scale = scale
        self.mean = mean
        self.darkcount = darkcount
        self._fg: Image | None = None

    def add(self, image: Image) -> None:
        '''Incorporate a new frame into the background estimate.

        Subtracts *darkcount* from *image* (without modifying the
        original array) and passes the result to the underlying median
        estimator.  The dark-count-corrected frame is also stored as
        the current foreground for :meth:`get`.

        Parameters
        ----------
        image : Image
            Input frame.
        '''
        image = image - self.darkcount
        super().add(image)
        self._fg = image

    def get(self) -> Image:
        '''Return the background-normalized frame.

        Divides the stored foreground by the current median background
        estimate.  Pixels where the background is zero are set to zero.
        If *scale* is ``True`` the result is multiplied by *mean* and
        returned as ``uint8``.

        Returns
        -------
        Image
            Normalized (and optionally scaled) frame.
        '''
        bg = super().get()
        result = np.zeros_like(self._fg, dtype=float)
        np.divide(self._fg, bg, out=result, where=(bg != 0))
        if self.scale:
            result = self.mean * result
        return result.astype(np.uint8)


class Normalize(_NormalizeMixin, Median):

    '''Normalize frames against a median background estimate.

    Combines :class:`_NormalizeMixin` with :class:`Median` to produce
    a background-subtracted, normalized image stream.  Background
    estimation uses the median-of-three algorithm; a new background
    estimate is available every ``3 ** order`` frames.

    Parameters
    ----------
    order : int
        Recursion depth for the median estimator.  Default: ``1``.
    scale : bool
        Scale normalized output to *mean*.  Default: ``True``.
    mean : float
        Target mean after scaling.  Default: ``100.0``.
    darkcount : int
        Camera dark-count offset.  Default: ``0``.
    '''


class SmoothNormalize(_NormalizeMixin, MoMedian):

    '''Normalize frames against a streaming median background estimate.

    Combines :class:`_NormalizeMixin` with :class:`MoMedian` to
    produce a background-subtracted, normalized image stream.
    Background estimation uses the rolling median-of-three algorithm;
    a new estimate is produced on every frame.

    Parameters
    ----------
    order : int
        Recursion depth for the median estimator.  Default: ``1``.
    scale : bool
        Scale normalized output to *mean*.  Default: ``True``.
    mean : float
        Target mean after scaling.  Default: ``100.0``.
    darkcount : int
        Camera dark-count offset.  Default: ``0``.
    '''
