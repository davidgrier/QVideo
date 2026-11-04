'''Image operations shared by filters and widgets.'''
import cv2
from QVideo.lib.videotypes import Image


__all__ = ['grayscale', 'to8bit']


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


def to8bit(image: Image, levels: tuple[float, float] | None = None) -> Image:
    '''Return a ``uint16`` frame as ``uint8``, black to white.

    Parameters
    ----------
    image : Image
        Frame of type ``uint16``, gray or color.
    levels : tuple[float, float], optional
        The pixel values that become 0 and 255; values outside them
        saturate.  The default is the whole range of the type, 0 to 65535.

    Returns
    -------
    Image
        Frame of type ``uint8`` and the shape of *image*.
    '''
    black, white = levels or (0, 65535)
    if black:
        image = cv2.subtract(image, black)      # saturates at zero
    return cv2.convertScaleAbs(image, alpha=255. / (white - black))
