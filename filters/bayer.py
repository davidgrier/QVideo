'''Bayer-mosaic demosaicing filter and companion Qt widget.'''
from typing import ClassVar
from qtpy import QtCore, QtWidgets
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter, FilterCode
from QVideo.lib.videotypes import Image
import cv2

__all__ = ['BayerFilter', 'QBayerFilter']


class BayerFilter(VideoFilter):

    '''Converts a Bayer mosaic to an RGB image.

    A camera in a Bayer pixel format (``BayerRG8``, ``BayerGB12``, ...)
    delivers the raw mosaic of its sensor as a single-channel frame, which
    looks like a gray image with a fine checkerboard.  This filter
    interpolates the missing colors (bilinear demosaicing) and returns an
    RGB frame.

    A single-channel frame cannot say whether it is a mosaic or a
    monochrome image, so the *pattern* is a setting: ``'Off'`` (the
    default) passes every frame through.  Choose the pattern that the
    camera's ``PixelFormat`` names.  Frames with 3 or 4 channels (RGB, or
    YUV that the camera has already converted) always pass through.

    A frame of more than 8 bits is converted at its own depth and keeps
    its black and white levels.

    Parameters
    ----------
    pattern : str
        ``'Off'`` or the name of the pattern in the GenICam pixel format
        of the camera, from the color of the first two pixels of the
        first two rows of the sensor: ``'BayerRG'``, ``'BayerGR'``,
        ``'BayerGB'`` or ``'BayerBG'``.  Default: ``'Off'``.
    '''

    deep = True

    #: The values of :attr:`pattern`.
    PATTERNS: ClassVar[tuple[str, ...]] = ('Off', 'BayerRG', 'BayerGR',
                                           'BayerGB', 'BayerBG')

    #: The OpenCV conversion for each pattern.  OpenCV names a pattern
    #: from the second row and column of the sensor, so its names differ
    #: from those of GenICam: the ``RG`` of GenICam is ``BG`` there.
    _CODES: ClassVar[dict[str, str]] = {'BayerRG': 'COLOR_BayerBG2RGB',
                                        'BayerGR': 'COLOR_BayerGB2RGB',
                                        'BayerGB': 'COLOR_BayerGR2RGB',
                                        'BayerBG': 'COLOR_BayerRG2RGB'}

    def __init__(self, pattern: str = 'Off') -> None:
        super().__init__()
        self.pattern = pattern

    @property
    def pattern(self) -> str:
        '''The Bayer pattern of the mosaic, or ``'Off'``.'''
        return self._pattern

    @pattern.setter
    def pattern(self, pattern: str) -> None:
        if pattern not in self.PATTERNS:
            raise ValueError(f'pattern must be one of {self.PATTERNS}; '
                             f'got {pattern!r}')
        self._pattern = pattern

    def get(self) -> Image | None:
        '''Return the demosaiced frame.

        Returns
        -------
        Image or None
            RGB image for a single-channel frame when a pattern is set,
            otherwise the frame unchanged; ``None`` if no frame has been
            added.
        '''
        pattern = self._pattern
        if self.data is None:
            return None
        if pattern == 'Off' or self.data.ndim != 2:
            return self.data
        return cv2.cvtColor(self.data, getattr(cv2, self._CODES[pattern]))

    def to_code(self) -> FilterCode:
        if self._pattern == 'Off':
            return FilterCode(imports=(), lines=['pass'],
                              comment='Bayer demosaicing is off')
        return FilterCode(
            imports={'import cv2'},
            lines=['if image.ndim == 2:',
                   f'    image = cv2.cvtColor(image, '
                   f'cv2.{self._CODES[self._pattern]})'],
            comment=f'demosaic a {self._pattern} mosaic',
        )


class QBayerFilter(QVideoFilter):

    '''Widget for :class:`BayerFilter`: a pull-down of Bayer patterns.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Bayer to RGB'
    display_category = 'Preprocessing'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Bayer to RGB', BayerFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._patternBox = QtWidgets.QComboBox()
        self._patternBox.addItems(BayerFilter.PATTERNS)
        self._patternBox.setCurrentText(self.videoFilter.pattern)
        self._layout.addWidget(self._patternBox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._patternBox.currentTextChanged.connect(self._setPattern)

    @QtCore.Slot(str)
    def _setPattern(self, text: str) -> None:
        self.videoFilter.pattern = text


if __name__ == '__main__':  # pragma: no cover
    QBayerFilter.example()
