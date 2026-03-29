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

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from QVideo.lib.videotypes import Image
import numpy as np
import warnings
import logging


logger = logging.getLogger(__name__)

__all__ = ['QTrackpyOverlay', 'QTrackpyWidget']


try:
    import trackpy as tp
except Exception:
    tp = None


class _TrackpyWorker(QtCore.QObject):
    '''Runs :func:`trackpy.locate` in a background thread.

    Parameters
    ----------
    diameter : int
        Expected particle diameter [pixels]. Must be odd.
    minmass : float
        Minimum integrated brightness to report a particle.

    Signals
    -------
    newData(object)
        Emitted after each locate call with the resulting
        :class:`pandas.DataFrame`, or ``None`` on error.
    '''

    newData = QtCore.pyqtSignal(object)

    def __init__(self, diameter: int = 11, minmass: float = 100.) -> None:
        super().__init__()
        if tp is None:
            raise ImportError(
                'trackpy is required for QTrackpyWidget.'
                '\n\tInstall it with: pip install trackpy')
        self.diameter = diameter
        self.minmass = minmass

    @property
    def diameter(self) -> int:
        '''Expected particle diameter [pixels] (always odd).'''
        return self._diameter

    @diameter.setter
    def diameter(self, value: int) -> None:
        self._diameter = int(value) | 1

    @QtCore.pyqtSlot(np.ndarray)
    def locate(self, image: Image) -> None:
        '''Run :func:`trackpy.locate` on *image* and emit :attr:`newData`.

        Parameters
        ----------
        image : Image
            Video frame to analyse.  Colour frames are converted to
            greyscale before processing.
        '''
        frame = (np.mean(image, axis=2).astype(np.uint8)
                 if image.ndim == 3 else image)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                features = tp.locate(frame, self._diameter, minmass=self.minmass)
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

    @QtCore.pyqtSlot(object)
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


class QTrackpyWidget(QtWidgets.QGroupBox):
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

    '''

    #: Emitted for each processed frame with the :func:`trackpy.locate`
    #: :class:`~pandas.DataFrame`, or ``None`` on error.
    newData = QtCore.pyqtSignal(object)
    _locate = QtCore.pyqtSignal(np.ndarray)

    def __init__(self,
                 parent: QtWidgets.QWidget | None = None,
                 diameter: int = 11,
                 minmass: float = 100.) -> None:
        if tp is None:
            raise ImportError(
                'trackpy is required for QTrackpyWidget.'
                '\n\tInstall it with: pip install trackpy')
        super().__init__('Trackpy', parent)
        self._source = None
        self._ready = True
        self._overlay = QTrackpyOverlay()
        self._worker = _TrackpyWorker(diameter=diameter, minmass=minmass)
        self._thread = QtCore.QThread(self)
        self._worker.moveToThread(self._thread)
        self._locate.connect(self._worker.locate)
        self._worker.newData.connect(self._onNewData)
        self._thread.start()
        self._setupUi()
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self._cleanup)

    def _setupUi(self) -> None:
        self.setCheckable(True)
        self.setChecked(False)
        self.setFlat(True)
        layout = QtWidgets.QFormLayout(self)
        layout.setContentsMargins(2, 5, 2, 5)

        self._diameterSpinBox = QtWidgets.QSpinBox()
        self._diameterSpinBox.setRange(3, 201)
        self._diameterSpinBox.setSingleStep(2)
        self._diameterSpinBox.setValue(self._worker.diameter)
        self._diameterSpinBox.valueChanged.connect(self._setDiameter)
        layout.addRow('Diameter', self._diameterSpinBox)

        self._minmassSpinBox = QtWidgets.QDoubleSpinBox()
        self._minmassSpinBox.setRange(0., 1e7)
        self._minmassSpinBox.setSingleStep(10.)
        self._minmassSpinBox.setValue(self._worker.minmass)
        self._minmassSpinBox.valueChanged.connect(self._setMinmass)
        layout.addRow('Min mass', self._minmassSpinBox)

        self.toggled.connect(self._overlay.setVisible)

    @property
    def source(self):
        '''The :class:`~QVideo.lib.QVideoSource.QVideoSource` being tracked.'''
        return self._source

    @source.setter
    def source(self, source) -> None:
        if self._source is not None:
            self._source.newFrame.disconnect(self._onNewFrame)
        self._source = source
        if source is not None:
            source.newFrame.connect(self._onNewFrame)

    @property
    def overlay(self) -> QTrackpyOverlay:
        '''The :class:`QTrackpyOverlay` graphics item for this widget.'''
        return self._overlay

    @QtCore.pyqtSlot(np.ndarray)
    def _onNewFrame(self, image: Image) -> None:
        if self._ready and self.isChecked():
            self._ready = False
            self._locate.emit(image)

    @QtCore.pyqtSlot(object)
    def _onNewData(self, features) -> None:
        self._ready = True
        self._overlay.setFeatures(features)
        self.newData.emit(features)

    @QtCore.pyqtSlot(int)
    def _setDiameter(self, value: int) -> None:
        odd = value | 1
        if odd != value:
            self._diameterSpinBox.blockSignals(True)
            self._diameterSpinBox.setValue(odd)
            self._diameterSpinBox.blockSignals(False)
        self._worker.diameter = odd

    @QtCore.pyqtSlot(float)
    def _setMinmass(self, value: float) -> None:
        self._worker.minmass = value

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop the worker thread when the widget is closed.'''
        self._cleanup()
        super().closeEvent(event)

    @QtCore.pyqtSlot()
    def _cleanup(self) -> None:
        self.source = None
        self._thread.quit()
        self._thread.wait()
