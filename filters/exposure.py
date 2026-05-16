'''Exposure correction filters (Log, Sigmoid, CLAHE) and companion Qt widget.'''
import logging
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np
import cv2

__all__ = ['ExposureFilter', 'QExposureFilter']

logger = logging.getLogger(__name__)


class ExposureFilter(AsyncVideoFilter):

    '''Exposure tone-mapping with three selectable methods.

    **Log** compresses the dynamic range via a logarithmic curve, lifting
    shadows without clipping highlights.  No parameters.

    **Sigmoid** applies a smooth S-curve centred at *cutoff* with steepness
    *gain*.  Low *gain* gives a gentle contrast boost; high *gain* approaches
    hard clipping.

    **CLAHE** (Contrast-Limited Adaptive Histogram Equalization) equalises
    local contrast within *tile_size* × *tile_size* tiles, capping
    amplification at *clip_limit* to suppress noise.  On colour input, CLAHE
    is applied to the L channel in LAB colour space so hue and saturation are
    preserved.

    Computation runs in a background thread via
    :class:`~QVideo.lib.AsyncVideoFilter.AsyncVideoFilter`, keeping the GUI
    responsive even for large frames.

    Parameters
    ----------
    method : str
        One of ``'Log'``, ``'Sigmoid'``, or ``'CLAHE'``.  Default: ``'Log'``.
    cutoff : float
        Sigmoid midpoint [0, 255].  Default: ``128.0``.
    gain : float
        Sigmoid steepness (≥ 0.1).  Default: ``10.0``.
    clip_limit : float
        CLAHE contrast-limit threshold (≥ 0.1).  Default: ``2.0``.
    tile_size : int
        CLAHE grid cell size in pixels (≥ 1).  Default: ``8``.
    '''

    METHODS = ('Log', 'Sigmoid', 'CLAHE')

    def __init__(self,
                 method: str = 'Log',
                 cutoff: float = 128.0,
                 gain: float = 10.0,
                 clip_limit: float = 2.0,
                 tile_size: int = 8) -> None:
        self._method = 'Log'
        self._cutoff = float(cutoff)
        self._gain = float(gain)
        self._clip_limit = float(clip_limit)
        self._tile_size = int(tile_size)
        self._clahe = cv2.createCLAHE(clipLimit=self._clip_limit,
                                       tileGridSize=(self._tile_size,
                                                     self._tile_size))
        self.method = method
        super().__init__()

    @property
    def method(self) -> str:
        '''Tone-mapping method: ``'Log'``, ``'Sigmoid'``, or ``'CLAHE'``.'''
        return self._method

    @method.setter
    def method(self, value: str) -> None:
        if value not in self.METHODS:
            logger.warning(f'method must be one of {self.METHODS}; ignoring')
            return
        self._method = value

    @property
    def cutoff(self) -> float:
        '''Sigmoid midpoint [0, 255].'''
        return self._cutoff

    @cutoff.setter
    def cutoff(self, value: float) -> None:
        self._cutoff = max(0.0, min(255.0, float(value)))

    @property
    def gain(self) -> float:
        '''Sigmoid steepness (≥ 0.1).'''
        return self._gain

    @gain.setter
    def gain(self, value: float) -> None:
        self._gain = max(0.1, float(value))

    @property
    def clip_limit(self) -> float:
        '''CLAHE contrast-limit threshold (≥ 0.1); rebuilds CLAHE object.'''
        return self._clip_limit

    @clip_limit.setter
    def clip_limit(self, value: float) -> None:
        self._clip_limit = max(0.1, float(value))
        self._clahe = cv2.createCLAHE(clipLimit=self._clip_limit,
                                       tileGridSize=(self._tile_size,
                                                     self._tile_size))

    @property
    def tile_size(self) -> int:
        '''CLAHE grid cell size in pixels (≥ 1); rebuilds CLAHE object.'''
        return self._tile_size

    @tile_size.setter
    def tile_size(self, value: int) -> None:
        self._tile_size = max(1, int(value))
        self._clahe = cv2.createCLAHE(clipLimit=self._clip_limit,
                                       tileGridSize=(self._tile_size,
                                                     self._tile_size))

    def process(self, image: Image) -> Image:
        '''Apply the selected tone-mapping method to *image*.

        Called in the background thread.

        Parameters
        ----------
        image : Image
            Input uint8 frame.

        Returns
        -------
        Image
            Tone-mapped uint8 frame.
        '''
        if self._method == 'Log':
            f = image.astype(np.float32)
            return np.clip(
                np.log1p(f) / np.log1p(255) * 255, 0, 255).astype(np.uint8)
        if self._method == 'Sigmoid':
            f = image.astype(np.float32)
            return np.clip(
                255 / (1 + np.exp(-self._gain * (f / 255 - self._cutoff / 255))),
                0, 255).astype(np.uint8)
        # CLAHE
        if image.ndim == 3:
            lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
            lab[:, :, 0] = self._clahe.apply(lab[:, :, 0])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        return self._clahe.apply(image)

    def to_code(self) -> 'FilterCode':
        from QVideo.lib.QVideoFilter import FilterCode
        if self._method == 'Log':
            return FilterCode(
                imports=frozenset({'import numpy as np'}),
                lines=[
                    '_f = image.astype(np.float32)',
                    'image = np.clip('
                    'np.log1p(_f) / np.log1p(255) * 255, 0, 255).astype(np.uint8)',
                ],
                comment='log exposure correction',
            )
        if self._method == 'Sigmoid':
            c = self._cutoff / 255
            return FilterCode(
                imports=frozenset({'import numpy as np'}),
                lines=[
                    '_f = image.astype(np.float32)',
                    f'image = np.clip('
                    f'255 / (1 + np.exp(-{self._gain} * (_f / 255 - {c:.6f}))), '
                    f'0, 255).astype(np.uint8)',
                ],
                comment=(f'sigmoid exposure, cutoff={self._cutoff}, '
                         f'gain={self._gain}'),
            )
        # CLAHE
        return FilterCode(
            imports=frozenset({'import cv2'}),
            lines=[
                f'_clahe = cv2.createCLAHE('
                f'clipLimit={self._clip_limit}, '
                f'tileGridSize=({self._tile_size}, {self._tile_size}))',
                'if image.ndim == 3:',
                '    _lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)',
                '    _lab[:, :, 0] = _clahe.apply(_lab[:, :, 0])',
                '    image = cv2.cvtColor(_lab, cv2.COLOR_LAB2RGB)',
                'else:',
                '    image = _clahe.apply(image)',
            ],
            comment=(f'CLAHE, clip={self._clip_limit}, '
                     f'tile={self._tile_size}'),
        )


class QExposureFilter(QVideoFilter):

    display_name = 'Exposure'
    display_category = 'Preprocessing'

    '''Widget for :class:`ExposureFilter` with a method selector and
    context-sensitive parameter spinboxes.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Exposure', ExposureFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._methodBox = QtWidgets.QComboBox()
        for m in ExposureFilter.METHODS:
            self._methodBox.addItem(m)
        self._layout.addWidget(self._methodBox)
        self._cutoffBox = SpinBox(value=self.filter.cutoff,
                                  bounds=(0.0, 255.0), step=1.0,
                                  prefix='cutoff ')
        self._layout.addWidget(self._cutoffBox)
        self._gainBox = SpinBox(value=self.filter.gain,
                                bounds=(0.1, 50.0), step=0.5,
                                prefix='gain ')
        self._layout.addWidget(self._gainBox)
        self._clipBox = SpinBox(value=self.filter.clip_limit,
                                bounds=(0.1, 40.0), step=0.5,
                                prefix='clip ')
        self._layout.addWidget(self._clipBox)
        self._tileBox = SpinBox(value=self.filter.tile_size,
                                bounds=(1, 64), step=1, int=True,
                                prefix='tile ')
        self._layout.addWidget(self._tileBox)
        self._updateVisibility(self.filter.method)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._methodBox.currentTextChanged.connect(self._setMethod)
        self._cutoffBox.valueChanged.connect(self._setCutoff)
        self._gainBox.valueChanged.connect(self._setGain)
        self._clipBox.valueChanged.connect(self._setClipLimit)
        self._tileBox.valueChanged.connect(self._setTileSize)

    def _updateVisibility(self, method: str) -> None:
        sigmoid = method == 'Sigmoid'
        clahe = method == 'CLAHE'
        self._cutoffBox.setVisible(sigmoid)
        self._gainBox.setVisible(sigmoid)
        self._clipBox.setVisible(clahe)
        self._tileBox.setVisible(clahe)

    @QtCore.Slot(str)
    def _setMethod(self, value: str) -> None:
        self.filter.method = value
        self._updateVisibility(value)

    @QtCore.Slot(object)
    def _setCutoff(self, value: float) -> None:
        self.filter.cutoff = value

    @QtCore.Slot(object)
    def _setGain(self, value: float) -> None:
        self.filter.gain = value

    @QtCore.Slot(object)
    def _setClipLimit(self, value: float) -> None:
        self.filter.clip_limit = value

    @QtCore.Slot(object)
    def _setTileSize(self, value: float) -> None:
        self.filter.tile_size = int(value)


if __name__ == '__main__':  # pragma: no cover
    QExposureFilter.example()
