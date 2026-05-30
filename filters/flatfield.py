'''Flat field normalization filter and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np


__all__ = ['FlatFieldFilter', 'QFlatFieldFilter']


class FlatFieldFilter(VideoFilter):

    '''Flat field normalization filter.

    Corrects pixel-wise sensitivity variation by dividing each frame
    by a stored flat field reference.  The reference is the mean of
    :attr:`nFrames` frames captured under uniform illumination,
    normalized so that its mean equals 1.0.  Division restores uniform
    response across the sensor.

    For best results, place this filter after
    :class:`~QVideo.filters.darkframe.DarkFrameFilter` in the
    pipeline.  When dark-subtracted frames are used during the
    reference capture the flat field is automatically dark-corrected,
    and subsequent frames arrive already dark-subtracted.

    Call :meth:`capture` to start accumulating the flat field
    reference.  Call :meth:`reset` to clear it.  Frames pass through
    unchanged until a reference is captured.

    Pixels where the normalized flat field is zero are passed through
    without correction.

    If the incoming frame shape does not match the stored reference
    :meth:`get` returns the raw frame until a new capture is
    performed.

    Emits :attr:`captured` when a new flat field capture completes.

    Parameters
    ----------
    nFrames : int
        Number of frames to average during capture.  Default: ``16``.
    '''

    captured = QtCore.Signal()

    def __init__(self, nFrames: int = 16) -> None:
        super().__init__()
        self._flat: np.ndarray | None = None
        self._accumulator: np.ndarray | None = None
        self._captureCount: int = 0
        self.nFrames = nFrames

    @property
    def nFrames(self) -> int:
        '''Number of frames averaged during capture (≥ 1).'''
        return self._nFrames

    @nFrames.setter
    def nFrames(self, value: int) -> None:
        self._nFrames = max(1, int(value))

    @property
    def isCapturing(self) -> bool:
        '''``True`` while a flat field capture is in progress.'''
        return self._captureCount > 0

    def capture(self) -> None:
        '''Start accumulating a flat field reference.

        Resets the accumulator and counts down :attr:`nFrames` calls
        to :meth:`add`.  :attr:`captured` is emitted on completion.
        '''
        self._accumulator = None
        self._captureCount = self._nFrames

    def reset(self) -> None:
        '''Clear the stored flat field reference and any ongoing capture.

        Frames pass through unchanged until a new capture completes.
        '''
        self._flat = None
        self._accumulator = None
        self._captureCount = 0

    def add(self, image: Image) -> None:
        '''Incorporate a new frame into the filter state.

        During a capture, accumulates frames into a running sum.  When
        the target count is reached the mean is normalized (divided by
        its own mean) and stored.  If the mean is zero, no reference is
        stored.  :attr:`captured` is emitted on completion.

        Parameters
        ----------
        image : Image
            Input frame.
        '''
        if self._captureCount > 0:
            if self._accumulator is None:
                self._accumulator = image.astype(np.float32)
            else:
                self._accumulator += image.astype(np.float32)
            self._captureCount -= 1
            if self._captureCount == 0:
                flat = self._accumulator / self._nFrames
                mean = float(flat.mean())
                self._flat = flat / mean if mean > 0 else None
                self._accumulator = None
                self.captured.emit()
        self.data = image

    def get(self) -> Image | None:
        '''Return the flat-field-corrected frame.

        Returns ``None`` before the first :meth:`add`, the raw frame
        if no reference is stored or if the frame shape does not match
        the reference, and the corrected (clipped) frame otherwise.
        Pixels where the flat field is zero pass through unchanged.

        Returns
        -------
        Image or None
        '''
        if self.data is None:
            return None
        if (self._flat is None
                or self.data.shape != self._flat.shape):
            return self.data
        safe = np.where(self._flat > 0, self._flat, 1.0)
        corrected = np.where(
            self._flat > 0,
            self.data.astype(np.float32) / safe,
            self.data.astype(np.float32))
        return np.clip(corrected, 0, 255).astype(np.uint8)


class QFlatFieldFilter(QVideoFilter):

    '''Widget for :class:`FlatFieldFilter` with capture controls.

    A checkable group box with a *frames* spinbox setting how many
    frames are averaged, a *Capture* button to start accumulation, and
    a *Reset* button to clear the stored reference.  The *Capture*
    button is disabled during accumulation and re-enabled on
    completion.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Flat Field'
    display_category = 'Calibration'

    def __init__(
            self,
            parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Flat Field', FlatFieldFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._layout.addWidget(QtWidgets.QLabel('frames'))
        self._nFramesBox = SpinBox(
            value=self.filter.nFrames,
            bounds=(1, 256), int=True)
        self._layout.addWidget(self._nFramesBox)
        self._captureButton = QtWidgets.QPushButton('Capture', self)
        self._layout.addWidget(self._captureButton)
        self._resetButton = QtWidgets.QPushButton('Reset', self)
        self._layout.addWidget(self._resetButton)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._nFramesBox.valueChanged.connect(self._setNFrames)
        self._captureButton.clicked.connect(self._capture)
        self._resetButton.clicked.connect(self._reset)
        self.filter.captured.connect(self._onCaptured)

    @QtCore.Slot(object)
    def _setNFrames(self, value: int) -> None:
        self.filter.nFrames = int(value)
        with QtCore.QSignalBlocker(self._nFramesBox):
            self._nFramesBox.setValue(self.filter.nFrames)

    @QtCore.Slot(bool)
    def _capture(self, _checked: bool = False) -> None:
        self._captureButton.setEnabled(False)
        self.filter.capture()

    @QtCore.Slot()
    def _onCaptured(self) -> None:
        self._captureButton.setEnabled(True)

    @QtCore.Slot(bool)
    def _reset(self, _checked: bool = False) -> None:
        self.filter.reset()


if __name__ == '__main__':  # pragma: no cover
    QFlatFieldFilter.example()
