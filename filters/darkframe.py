'''Dark frame subtraction filter and companion Qt widget.'''
from QVideo.lib.QReferenceFilter import ReferenceFilter, QReferenceFilter
from QVideo.lib.videotypes import Image
import numpy as np


__all__ = ['DarkFrameFilter', 'QDarkFrameFilter']


class DarkFrameFilter(ReferenceFilter):

    '''Dark frame subtraction filter.

    Subtracts a stored dark frame from every incoming image to remove
    camera baseline noise: thermal electrons, fixed-pattern noise, and
    amplifier offset.

    Call :meth:`~QVideo.lib.QReferenceFilter.ReferenceFilter.capture` to
    start averaging :attr:`nFrames` frames with no illumination.  The mean
    becomes the dark reference, and every subsequent frame is
    dark-subtracted, with negative values clipped to zero.  The base class
    describes the capture, :meth:`reset` and the frames that pass through
    unchanged.

    Parameters
    ----------
    nFrames : int
        Number of frames to average during capture.  Default: ``16``.
    '''

    def _makeReference(self, mean: np.ndarray) -> np.ndarray:
        return mean.astype(np.uint8)

    def _correct(self, frame: Image, reference: np.ndarray) -> Image:
        difference = frame.astype(np.int16) - reference.astype(np.int16)
        return np.clip(difference, 0, 255).astype(np.uint8)


class QDarkFrameFilter(QReferenceFilter):

    '''Widget for :class:`DarkFrameFilter` with capture controls.

    A checkable group box with a *frames* spinbox setting how many
    frames are averaged, a *Capture* button to start accumulation, and
    a *Reset* button to clear the stored dark frame.  The *Capture*
    button is disabled during accumulation and re-enabled on
    completion.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Dark Frame'
    filterClass = DarkFrameFilter


if __name__ == '__main__':  # pragma: no cover
    QDarkFrameFilter.example()
