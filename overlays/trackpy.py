'''Real-time particle tracking overlay using trackpy.

References
----------
Allan, D. B., Caswell, T., Keim, N. C., van der Wel, C. M., &
Verweij, R. W. trackpy: Fast, Friendly Particle Tracking in Python.
Zenodo. https://doi.org/10.5281/zenodo.9971

Crocker, J. C., & Grier, D. G. (1996). Methods of digital video
microscopy for colloidal studies. Journal of Colloid and Interface
Science, 179(1), 298-310. https://doi.org/10.1006/jcis.1996.0217
'''

from qtpy import QtCore, QtWidgets
import pyqtgraph as pg
from QVideo.lib import QOverlayWidget
from QVideo.lib.videotypes import Image
import numpy as np
import warnings
import logging


logger = logging.getLogger(__name__)

__all__ = ['QTrackpyOverlay', 'QTrackpyWidget']


_importError = None
try:
    import trackpy as tp
except Exception as ex:  # a broken installation raises more than ImportError
    tp = None
    _importError = ex


def _option(key: str, doc: str) -> property:
    '''A property of the worker that reads and writes a locate option.'''
    return property(lambda self: self._opts[key],
                    lambda self, value: self._opts.__setitem__(key, value),
                    doc=doc)


class _TrackpyWorker(QtCore.QObject):
    '''Runs :func:`trackpy.locate` in a background thread.

    Parameters
    ----------
    diameter : int
        Expected particle diameter [pixels]. Must be odd.
    minmass : float
        Minimum integrated brightness to report a particle.
    separation : float or None
        Minimum separation of particle centers [pixels]; ``None`` lets
        trackpy choose.
    noiseSize : int
        Width of the Gaussian blur that suppresses noise [pixels].
    invert : bool
        Look for dark particles on a bright background.

    Signals
    -------
    newData(object)
        Emitted after each locate call with the resulting
        :class:`pandas.DataFrame`, or ``None`` on error.
    '''

    newData = QtCore.Signal(object)

    minmass = _option('minmass', 'Minimum integrated brightness.')
    separation = _option('separation', 'Minimum separation of centers.')
    noiseSize = _option('noise_size', 'Width of the noise filter [pixels].')
    invert = _option('invert', 'Look for dark particles.')

    def __init__(self,
                 diameter: int = 11,
                 minmass: float = 100.,
                 separation: float | None = None,
                 noiseSize: int = 1,
                 invert: bool = False) -> None:
        super().__init__()
        if tp is None:
            raise ImportError(
                'trackpy is required for QTrackpyWidget.'
                '\n\tInstall it with: pip install trackpy') from _importError
        self.diameter = diameter
        self._opts = {'minmass': minmass, 'separation': separation,
                      'noise_size': noiseSize, 'characterize': False,
                      'invert': invert}

    @property
    def diameter(self) -> int:
        '''Expected particle diameter [pixels] (always odd).'''
        return self._diameter

    @diameter.setter
    def diameter(self, value: int) -> None:
        self._diameter = int(value) | 1

    @QtCore.Slot(np.ndarray)
    def process(self, image: Image) -> None:
        '''Run :func:`trackpy.locate` on *image* and emit :attr:`newData`.

        Parameters
        ----------
        image : Image
            Video frame to analyze.  Color frames are converted to
            grayscale before processing.
        '''
        frame = (np.mean(image, axis=2).astype(np.uint8)
                 if image.ndim == 3 else image)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                features = tp.locate(frame, self._diameter, **self._opts)
        except Exception as exc:
            logger.warning(f'trackpy.locate() failed: {exc}')
            features = None
        self.newData.emit(features)


class QTrackpyOverlay(pg.ScatterPlotItem):
    '''Scatter-plot overlay that marks trackpy particle positions.

    A :class:`pyqtgraph.ScatterPlotItem` pre-configured for particle
    display.  Add it to a :class:`~QVideo.lib.QVideoScreen.QVideoScreen`
    via ``screen.view.addItem(overlay)``, or use
    ``screen.addOverlay(widget.overlay)``.
    '''

    def __init__(self, **kwargs) -> None:
        defaults = dict(pen=pg.mkPen('r'), brush=pg.mkBrush(None),
                        symbol='o', size=15, pxMode=True)
        defaults.update(kwargs)
        super().__init__(**defaults)

    @QtCore.Slot(object)
    def setFeatures(self, features) -> None:
        '''Update scatter positions from a trackpy DataFrame.

        Parameters
        ----------
        features : pandas.DataFrame or None
            DataFrame with ``x`` and ``y`` columns returned by
            :func:`trackpy.locate`.  ``None`` or an empty frame clears
            the overlay.
        '''
        if features is None or len(features) == 0:
            self.setData([], [])
        else:
            self.setData(x=features['x'].to_numpy(),
                         y=features['y'].to_numpy())


class QTrackpyWidget(QOverlayWidget):
    '''Control widget for the trackpy particle-tracking overlay.

    Runs :func:`trackpy.locate` in a background thread and renders
    detected particle positions as a :class:`QTrackpyOverlay` scatter
    plot on a :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.

    Use ``screen.addOverlay(widget.overlay)`` to register the overlay
    graphics item with a screen, and set :attr:`source` to supply video frames.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    diameter : int
        Initial expected particle diameter [pixels]. Must be odd.
        Default: ``11``.
    minmass : float
        Initial minimum integrated brightness. Default: ``100``.
    separation : float or None
        Minimum separation between particle centers [pixels].  ``None``
        (default) lets trackpy choose (diameter + 1).
    noise_size : int
        Radius of the Gaussian blur applied for noise suppression [pixels].
        Default: ``1``.
    invert : bool
        If ``True``, invert the image before locating particles (for dark
        particles on a bright background). Default: ``False``.

    '''

    def __init__(self,
                 parent: QtWidgets.QWidget | None = None,
                 diameter: int = 11,
                 minmass: float = 100.,
                 separation: float | None = None,
                 noise_size: int = 1,
                 invert: bool = False) -> None:
        worker = _TrackpyWorker(diameter, minmass, separation, noise_size,
                                invert)
        super().__init__('Trackpy', QTrackpyOverlay(), worker, parent)

    def _setupUi(self) -> None:
        super()._setupUi()
        worker = self._worker

        self._diameterSpinBox = QtWidgets.QSpinBox()
        self._diameterSpinBox.setRange(3, 201)
        self._diameterSpinBox.setSingleStep(2)
        self._diameterSpinBox.setValue(worker.diameter)
        self._diameterSpinBox.valueChanged.connect(self._setDiameter)
        self._layout.addRow('Diameter', self._diameterSpinBox)

        self._minmassSpinBox = QtWidgets.QDoubleSpinBox()
        self._minmassSpinBox.setRange(0., 1e7)
        self._minmassSpinBox.setSingleStep(10.)
        self._minmassSpinBox.setValue(worker.minmass)
        self._minmassSpinBox.valueChanged.connect(self._setMinmass)
        self._layout.addRow('Min mass', self._minmassSpinBox)

        self._separationSpinBox = QtWidgets.QDoubleSpinBox()
        self._separationSpinBox.setRange(0., 1000.)
        self._separationSpinBox.setSingleStep(1.)
        self._separationSpinBox.setSpecialValueText('auto')
        self._separationSpinBox.setValue(worker.separation or 0.)
        self._separationSpinBox.valueChanged.connect(self._setSeparation)
        self._layout.addRow('Separation', self._separationSpinBox)

        self._noiseSizeSpinBox = QtWidgets.QSpinBox()
        self._noiseSizeSpinBox.setRange(1, 20)
        self._noiseSizeSpinBox.setValue(worker.noiseSize)
        self._noiseSizeSpinBox.valueChanged.connect(self._setNoiseSize)
        self._layout.addRow('Noise size', self._noiseSizeSpinBox)

        self._invertCheckBox = QtWidgets.QCheckBox()
        self._invertCheckBox.setChecked(worker.invert)
        self._invertCheckBox.toggled.connect(self._setInvert)
        self._layout.addRow('Invert', self._invertCheckBox)

    @QtCore.Slot(int)
    def _setDiameter(self, value: int) -> None:
        odd = value | 1
        if odd != value:
            self._diameterSpinBox.blockSignals(True)
            self._diameterSpinBox.setValue(odd)
            self._diameterSpinBox.blockSignals(False)
        self._worker.diameter = odd

    @QtCore.Slot(float)
    def _setMinmass(self, value: float) -> None:
        self._worker.minmass = value

    @QtCore.Slot(float)
    def _setSeparation(self, value: float) -> None:
        self._worker.separation = None if value == 0. else value

    @QtCore.Slot(int)
    def _setNoiseSize(self, value: int) -> None:
        self._worker.noiseSize = value

    @QtCore.Slot(bool)
    def _setInvert(self, checked: bool) -> None:
        self._worker.invert = checked
