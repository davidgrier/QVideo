'''Flat field normalization filter and companion Qt widget.'''
from QVideo.lib.QReferenceFilter import ReferenceFilter, QReferenceFilter
from QVideo.lib.videotypes import Image
import numpy as np


__all__ = ['FlatFieldFilter', 'QFlatFieldFilter']


class FlatFieldFilter(ReferenceFilter):

    '''Flat field normalization filter.

    Corrects pixel-wise sensitivity variation by dividing each frame
    by a stored flat field reference.  The reference is the mean of
    :attr:`nFrames` frames captured under uniform illumination,
    normalized so that its mean equals 1.0.  Division restores uniform
    response across the sensor.  If the mean is zero there is no
    reference, and pixels where the normalized flat field is zero are
    passed through without correction.

    For best results, place this filter after
    :class:`~QVideo.filters.darkframe.DarkFrameFilter` in the
    pipeline.  When dark-subtracted frames are used during the
    reference capture the flat field is automatically dark-corrected,
    and subsequent frames arrive already dark-subtracted.

    The base class describes the capture, :meth:`reset` and the frames
    that pass through unchanged.

    Parameters
    ----------
    nFrames : int
        Number of frames to average during capture.  Default: ``16``.
    '''

    def _makeReference(self, mean: np.ndarray) -> np.ndarray | None:
        scale = float(mean.mean())
        return mean / scale if scale > 0 else None

    def _correct(self, frame: Image, reference: np.ndarray) -> Image:
        valid = reference > 0
        image = frame.astype(np.float32)
        corrected = np.where(valid, image / np.where(valid, reference, 1.0),
                             image)
        return np.clip(corrected, 0, 255).astype(np.uint8)


class QFlatFieldFilter(QReferenceFilter):

    '''Widget for :class:`FlatFieldFilter` with capture controls.

    A checkable group box with a *frames* spinbox setting how many
    frames are averaged, a *Capture* button to start accumulation, and
    a *Reset* button to clear the stored reference.  The *Capture*
    button is disabled during accumulation and re-enabled on
    completion.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Flat Field'
    filterClass = FlatFieldFilter


if __name__ == '__main__':  # pragma: no cover
    QFlatFieldFilter.example()
