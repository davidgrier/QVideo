'''Artistic non-photorealistic filters and companion Qt widgets.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter, FilterCode
from QVideo.lib.videotypes import Image
import cv2


__all__ = ['PencilSketchFilter', 'QPencilSketchFilter',
           'CartoonFilter', 'QCartoonFilter']


#: The lines of a :class:`FilterCode` that make ``image`` three channels.
_COLOR_LINES = ('if image.ndim == 2:',
              '    image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)')


def _ensure_color(image: Image) -> Image:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    return image


class PencilSketchFilter(VideoFilter):

    '''Pencil-drawing effect via OpenCV non-photorealistic rendering.

    Applies ``cv2.pencilSketch`` to produce a
    hand-drawn pencil look without blocking the GUI.  Grayscale input
    is promoted to three channels before processing.

    Parameters
    ----------
    sigma_s : float
        Spatial extent of the filter in pixels.  Range 1–200.
        Default: ``60.0``.
    sigma_r : float
        How much color variation is treated as part of the same region.
        Range 0–1.  Default: ``0.07``.
    shade_factor : float
        Darkness of pencil strokes.  Range 0–0.1.  Default: ``0.05``.
    gray : bool
        If ``True``, return the single-channel grayscale sketch.
        If ``False``, return the three-channel color sketch.
        Default: ``False``.
    '''

    def __init__(self,
                 sigma_s: float = 60.,
                 sigma_r: float = 0.07,
                 shade_factor: float = 0.05,
                 gray: bool = False) -> None:
        self.sigma_s = float(sigma_s)
        self.sigma_r = float(sigma_r)
        self.shade_factor = float(shade_factor)
        self.gray = bool(gray)
        super().__init__()

    def process(self, image: Image) -> Image:
        '''Apply the pencil-sketch transform.

        Parameters
        ----------
        image : Image
            Input frame (gray or RGB uint8).

        Returns
        -------
        Image
            uint8 pencil-sketch frame.
        '''
        color = _ensure_color(image)
        gray_out, color_out = cv2.pencilSketch(
            color,
            sigma_s=self.sigma_s,
            sigma_r=self.sigma_r,
            shade_factor=self.shade_factor,
        )
        return gray_out if self.gray else color_out

    def to_code(self) -> FilterCode:
        ss, sr, sf = self.sigma_s, self.sigma_r, self.shade_factor
        target = 'image, _' if self.gray else '_, image'
        return FilterCode(
            imports={'import cv2'},
            lines=[*_COLOR_LINES,
                   f'{target} = cv2.pencilSketch(image, sigma_s={ss}, '
                   f'sigma_r={sr}, shade_factor={sf})'],
            comment=f'pencil sketch, σ_s={ss}, σ_r={sr}, shade={sf}',
        )



class CartoonFilter(VideoFilter):

    '''Cartoon/painterly stylization via OpenCV non-photorealistic rendering.

    Applies ``cv2.stylization``, smoothing
    low-contrast regions while preserving edges to produce a
    watercolor/cartoon look.  Grayscale input is promoted to three channels before
    processing.

    Parameters
    ----------
    sigma_s : float
        Spatial extent of the filter in pixels.  Range 1–200.
        Default: ``150.0``.
    sigma_r : float
        How much color variation is treated as part of the same region.
        Range 0–1.  Default: ``0.45``.
    '''

    def __init__(self,
                 sigma_s: float = 150.,
                 sigma_r: float = 0.45) -> None:
        self.sigma_s = float(sigma_s)
        self.sigma_r = float(sigma_r)
        super().__init__()

    def process(self, image: Image) -> Image:
        '''Apply cartoon stylization.

        Parameters
        ----------
        image : Image
            Input frame (gray or RGB uint8).

        Returns
        -------
        Image
            uint8 RGB stylized frame.
        '''
        color = _ensure_color(image)
        return cv2.stylization(color, sigma_s=self.sigma_s, sigma_r=self.sigma_r)

    def to_code(self) -> FilterCode:
        ss, sr = self.sigma_s, self.sigma_r
        return FilterCode(
            imports={'import cv2'},
            lines=[*_COLOR_LINES,
                   f'image = cv2.stylization(image, sigma_s={ss}, '
                   f'sigma_r={sr})'],
            comment=f'cartoon stylization, σ_s={ss}, σ_r={sr}',
        )



class QPencilSketchFilter(QVideoFilter):

    '''Widget for :class:`PencilSketchFilter` with parameter spinboxes.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Pencil Sketch'
    display_category = 'Artistic'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Pencil Sketch', PencilSketchFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        f = self.videoFilter
        self._sigmaS = SpinBox(value=f.sigma_s,
                               bounds=(1., 200.), step=5.,
                               prefix='σ_s ')
        self._sigmaR = SpinBox(value=f.sigma_r,
                               bounds=(0.01, 1.0), step=0.01,
                               prefix='σ_r ')
        self._shade = SpinBox(value=f.shade_factor,
                              bounds=(0., 0.1), step=0.005,
                              prefix='shade ')
        self._grayBox = QtWidgets.QCheckBox('Gray')
        self._grayBox.setChecked(f.gray)
        for w in (self._sigmaS, self._sigmaR, self._shade, self._grayBox):
            self._layout.addWidget(w)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._sigmaS.valueChanged.connect(self._setSigmaS)
        self._sigmaR.valueChanged.connect(self._setSigmaR)
        self._shade.valueChanged.connect(self._setShade)
        self._grayBox.toggled.connect(self._setGray)

    @QtCore.Slot(object)
    def _setSigmaS(self, value: float) -> None:
        self.videoFilter.sigma_s = float(value)

    @QtCore.Slot(object)
    def _setSigmaR(self, value: float) -> None:
        self.videoFilter.sigma_r = float(value)

    @QtCore.Slot(object)
    def _setShade(self, value: float) -> None:
        self.videoFilter.shade_factor = float(value)

    @QtCore.Slot(bool)
    def _setGray(self, checked: bool) -> None:
        self.videoFilter.gray = checked


class QCartoonFilter(QVideoFilter):

    '''Widget for :class:`CartoonFilter` with sigma spinboxes.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Cartoon'
    display_category = 'Artistic'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Cartoon', CartoonFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        f = self.videoFilter
        self._sigmaS = SpinBox(value=f.sigma_s,
                               bounds=(1., 200.), step=5.,
                               prefix='σ_s ')
        self._sigmaR = SpinBox(value=f.sigma_r,
                               bounds=(0.01, 1.0), step=0.01,
                               prefix='σ_r ')
        self._layout.addWidget(self._sigmaS)
        self._layout.addWidget(self._sigmaR)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._sigmaS.valueChanged.connect(self._setSigmaS)
        self._sigmaR.valueChanged.connect(self._setSigmaR)

    @QtCore.Slot(object)
    def _setSigmaS(self, value: float) -> None:
        self.videoFilter.sigma_s = float(value)

    @QtCore.Slot(object)
    def _setSigmaR(self, value: float) -> None:
        self.videoFilter.sigma_r = float(value)


if __name__ == '__main__':  # pragma: no cover
    QCartoonFilter.example()
