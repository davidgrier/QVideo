'''Blob-coloring filter using connected-component labelling.'''
from qtpy import QtCore, QtWidgets
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import cv2
import numpy as np


__all__ = ['BlobFilter', 'QBlobFilter']


class BlobFilter(VideoFilter):

    '''Blob-coloring filter.

    Labels connected foreground regions in a binary frame and renders each
    blob in a distinct hue using OpenCV's HSV colour space.

    Notes
    -----
    The input frame is expected to be a binary (uint8) image where non-zero
    pixels form the foreground.  :func:`cv2.connectedComponents` assigns an
    integer label to each connected region; label 0 is background.

    Labels are mapped linearly to the hue channel (0–179 in OpenCV) and
    merged with a full-saturation, full-value channel to produce an HSV
    image that is then converted to BGR.  Background pixels (label 0) are
    forced to black after the colour conversion.

    The returned frame is always three-channel BGR uint8, with the same
    spatial dimensions as the input.
    '''

    def get(self) -> Image | None:
        '''Return the blob-coloured frame.

        Returns
        -------
        Image or None
            BGR image in which each connected foreground region is
            rendered in a distinct hue, or ``None`` if no frame has
            been added yet.
        '''
        if self.data is None:
            return None
        nblobs, labels = cv2.connectedComponents(self.data)
        hues = np.uint8(179 * labels / np.max(labels))
        blank = 255 * np.ones_like(hues)
        img = cv2.merge([hues, blank, blank])
        img = cv2.cvtColor(img, cv2.COLOR_HSV2BGR)
        img[hues == 0] = 0
        return img


class QBlobFilter(QVideoFilter):

    '''Widget wrapper for :class:`BlobFilter`.

    Displays the filter as a checkable group box.  No adjustable
    parameters are exposed; checking the box enables the filter.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Blob', BlobFilter())


if __name__ == '__main__':  # pragma: no cover
    QBlobFilter.example()
