'''Intensity-inversion filter and companion Qt widget.'''
from qtpy import QtWidgets
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import cv2


__all__ = ['InvertFilter', 'QInvertFilter']


class InvertFilter(VideoFilter):

    '''Inverts pixel intensities: black becomes white and vice versa.

    Applies ``255 - pixel`` to every channel of every pixel, turning a
    black-on-white image into white-on-black (and back again).  Has no
    parameters.
    '''

    def get(self) -> Image | None:
        '''Return the intensity-inverted frame.

        Returns
        -------
        Image or None
            Inverted uint8 image, or ``None`` if no frame has been added.
        '''
        if self.data is None:
            return None
        return cv2.bitwise_not(self.data)

    def to_code(self) -> 'FilterCode':
        from QVideo.lib.QVideoFilter import FilterCode
        return FilterCode(
            imports=frozenset({'import cv2'}),
            lines=['image = cv2.bitwise_not(image)'],
            comment='intensity inversion',
        )


class QInvertFilter(QVideoFilter):

    '''Widget for :class:`InvertFilter`.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Invert'
    display_category = 'Preprocessing'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Invert', InvertFilter())


if __name__ == '__main__':  # pragma: no cover
    QInvertFilter.example()
