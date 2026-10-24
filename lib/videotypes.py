'''Shared types used across QVideo.'''
from dataclasses import dataclass
from time import perf_counter, time
from typing import TypeAlias
from numpy.typing import NDArray
import numpy as np

Image: TypeAlias = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class FrameInfo:
    '''Metadata that accompanies a video frame.

    Emitted with every frame by :attr:`QVideoSource.newFrame`.  Instances
    are immutable, so one object can be shared safely among consumers
    on different threads.

    Parameters
    ----------
    index : int
        Number of frames successfully read since the source started;
        the first frame has index 0.  A gap between consecutive
        indices seen by a consumer means that consumer missed frames.
    timestamp : float
        Host time at which the frame was read [s], from
        :func:`time.perf_counter`, taken in the capture thread
        immediately after the camera returned the frame.  The clock is
        monotonic and its zero is arbitrary; compare timestamps with each
        other, or use :attr:`wallclock` for an absolute time.
    hardware_timestamp : float | None
        The camera's own timestamp for the frame [s], in the camera's
        native clock, or ``None`` if the camera does not provide one.
    '''

    index: int
    timestamp: float
    hardware_timestamp: float | None = None

    @property
    def wallclock(self) -> float:
        '''UNIX time at which the frame was captured [s].'''
        return time() - perf_counter() + self.timestamp


__all__ = ['Image', 'FrameInfo']
