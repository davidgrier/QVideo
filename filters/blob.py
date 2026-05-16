'''Blob-coloring filter using connected-component labeling.'''
from qtpy import QtWidgets
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image
import cv2
import numpy as np


__all__ = ['BlobFilter', 'QBlobFilter']


class BlobFilter(AsyncVideoFilter):

    '''Blob-coloring filter.

    Labels connected foreground regions in a binary frame and renders each
    blob in a distinct hue using OpenCV's HSV color space.  The labeling
    runs in a background thread so that large frames do not stall the GUI.

    Notes
    -----
    The input frame is expected to be a binary (uint8) image where non-zero
    pixels form the foreground.  :func:`cv2.connectedComponents` assigns an
    integer label to each connected region; label 0 is background.

    Labels are mapped linearly to the hue channel (0–179 in OpenCV) and
    merged with a full-saturation, full-value channel to produce an HSV
    image that is then converted to BGR.  Background pixels (label 0) are
    forced to black after the color conversion.

    The returned frame is always three-channel BGR uint8, with the same
    spatial dimensions as the input.  If the input contains no foreground
    pixels a black BGR frame is returned.
    '''

    def process(self, image: Image) -> Image:
        '''Label connected components and render each blob in a distinct hue.

        Parameters
        ----------
        image : Image
            Binary (uint8) input frame.

        Returns
        -------
        Image
            BGR image with each connected foreground region rendered in a
            distinct hue.  Background pixels are black.
        '''
        _, labels = cv2.connectedComponents(image)
        max_label = int(np.max(labels))
        if max_label == 0:
            return np.zeros((*image.shape, 3), dtype=np.uint8)
        hues = np.uint8(179 * labels / max_label)
        blank = 255 * np.ones_like(hues)
        img = cv2.merge([hues, blank, blank])
        img = cv2.cvtColor(img, cv2.COLOR_HSV2BGR)
        img[hues == 0] = 0
        return img


class QBlobFilter(QVideoFilter):

    display_name = 'Blob'
    display_category = 'Segmentation'

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
