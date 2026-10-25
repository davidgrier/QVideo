'''Image operations shared by filters and widgets.'''
import cv2
from QVideo.lib.videotypes import Image


__all__ = ['grayscale']


def grayscale(image: Image) -> Image:
    '''Return the luminance of an RGB frame as a ``uint8`` image.

    Frames are RGB ordered.  The luminance is the standard
    ``0.299 R + 0.587 G + 0.114 B``, so a monochrome image replicated into
    three channels comes back unchanged.  A frame that is already gray is
    returned as is.

    Parameters
    ----------
    image : Image
        Gray frame of shape ``(H, W)`` or color frame of shape
        ``(H, W, 3)`` or ``(H, W, 4)``.

    Returns
    -------
    Image
        Gray frame of shape ``(H, W)``.
    '''
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 \
        else image
