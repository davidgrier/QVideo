'''Image operations shared by filters and widgets.'''
from typing import Any, cast

import cv2
import numpy as np
from qtpy import QtGui
from QVideo.lib.videotypes import Image


__all__ = ['grayscale', 'to8bit', 'stretch16', 'save_image', 'AutoLevels',
           'ImageFormat']

#: The image formats: ``QImage.Format`` in PyQt6, ``QImage`` in PyQt5.
ImageFormat: Any = getattr(QtGui.QImage, 'Format', QtGui.QImage)

#: The file types that hold 16 bit gray.
_DEEP_FORMATS = ('.png', '.tif', '.tiff')


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
    return cast(Image, cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)) \
        if image.ndim == 3 else image


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
        # saturates at zero
        image = cv2.subtract(image, black)  # pyright: ignore[reportCallIssue, reportArgumentType]
    return cast(Image, cv2.convertScaleAbs(
        image, alpha=255. / (white - black)))


def stretch16(image: Image, levels: tuple[float, float] | None = None
              ) -> Image:
    '''Return a ``uint16`` frame with *levels* stretched to the full range.

    A 12 bit camera sends counts from 0 to 4095, which a viewer of 16 bit
    images shows as nearly black.  The pixel value that is white becomes
    65535 and the one that is black becomes 0.

    Parameters
    ----------
    image : Image
        Frame of type ``uint16``, gray or color.
    levels : tuple[float, float], optional
        The pixel values that become 0 and 65535; values outside them
        saturate.  The default is the whole range of the type, which
        leaves the frame as it is.

    Returns
    -------
    Image
        Frame of type ``uint16`` and the shape of *image*.
    '''
    black, white = levels or (0, 65535)
    if (black, white) == (0, 65535):
        return image
    scaled = (image.astype(np.float32) - black) * (65535. / (white - black))
    return cast(Image, np.rint(np.clip(scaled, 0, 65535)).astype(np.uint16))


def save_image(image: Image, filename: str,
               levels: tuple[float, float] | None = None) -> None:
    '''Write *image* to *filename*, in the format of its extension.

    Parameters
    ----------
    image : Image
        Gray ``(H, W)``, color ``(H, W, 3)`` or ``(H, W, 4)``; ``uint8``,
        or ``uint16`` from a camera of more than 8 bits.
    filename : str
        Destination path.  Qt infers the format from the extension.
    levels : tuple[float, float], optional
        The pixel values of a ``uint16`` image that are black and white.
        The default is the whole range.

    Raises
    ------
    ValueError
        If the type or the shape of *image* cannot be saved.
    OSError
        If the file cannot be written.

    Notes
    -----
    A gray ``uint16`` image is saved with 16 bits to a PNG or TIFF file,
    stretched so that *levels* run from 0 to 65535 (a 12 bit image would look
    black otherwise).  Any other file, and a color image, gets 8 bits
    between *levels*.
    '''
    if image.dtype not in (np.uint8, np.uint16):
        raise ValueError(f'unsupported dtype {image.dtype}; '
                         'expected uint8 or uint16')
    if not (image.ndim == 2
            or (image.ndim == 3 and image.shape[2] in (3, 4))):
        raise ValueError(f'unsupported image shape {image.shape}')
    deep = False
    if image.dtype == np.uint16:
        deep = (image.ndim == 2
                and str(filename).lower().endswith(_DEEP_FORMATS))
        image = (stretch16(image, levels) if deep
                 else to8bit(image, levels))
    image = np.ascontiguousarray(image)
    h, w = image.shape[:2]
    if deep:
        fmt, step = ImageFormat.Format_Grayscale16, 2 * w
    elif image.ndim == 2:
        fmt, step = ImageFormat.Format_Grayscale8, w
    elif image.shape[2] == 3:
        fmt, step = ImageFormat.Format_RGB888, 3 * w
    else:
        fmt, step = ImageFormat.Format_RGBA8888, 4 * w
    if not QtGui.QImage(image.tobytes(), w, h, step, fmt).save(str(filename)):
        raise OSError(f'cannot write {str(filename)!r}')


class AutoLevels:
    '''Black and white levels from the percentiles of the frames shown.

    The percentiles come from a subsample of every few frames, and the
    levels move a third of the way to each new estimate, so that a picture
    does not flicker.  The screen and the notebook display use the same
    rule.

    Parameters
    ----------
    percentiles : tuple[float, float]
        The percentiles that are black and white: ``0 <= low < high <= 100``.
    every : int
        Frames between estimates.
    sample : int
        About how many pixels of a frame make an estimate.

    Raises
    ------
    ValueError
        If the percentiles are not ``0 <= low < high <= 100``.
    '''

    def __init__(self, percentiles: tuple[float, float] = (1., 99.),
                 every: int = 5, sample: int = 20000) -> None:
        low, high = percentiles
        if not 0 <= low < high <= 100:
            raise ValueError(
                'the percentiles must satisfy 0 <= low < high <= 100: '
                f'{percentiles}')
        self.percentiles = (float(low), float(high))
        self.every = every
        self.sample = sample
        self._levels: tuple[float, float] | None = None
        self._count = 0

    def reset(self) -> None:
        '''Forget the levels, so that the next frame sets them.'''
        self._levels = None
        self._count = 0

    def __call__(self, image: Image) -> tuple[float, float]:
        '''Return the levels for *image*, smoothed over the frames.'''
        self._count += 1
        if self._levels is None or self._count % self.every == 0:
            step = max(1, int(np.sqrt(image.shape[0] * image.shape[1]
                                      / self.sample)))
            low, high = np.percentile(image[::step, ::step],
                                      self.percentiles)
            if high <= low:
                high = low + 1
            if self._levels is None:
                self._levels = (float(low), float(high))
            else:
                old = self._levels
                self._levels = (old[0] + (low - old[0]) / 3,
                                old[1] + (high - old[1]) / 3)
        return self._levels
