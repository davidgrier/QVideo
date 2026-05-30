'''Dark frame subtraction filter and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
import numpy as np


__all__ = ['DarkFrameFilter', 'QDarkFrameFilter']


class DarkFrameFilter(VideoFilter):

    '''Dark frame subtraction filter.

    Subtracts a stored dark frame from every incoming image to remove
    camera baseline noise: thermal electrons, fixed-pattern noise, and
    amplifier offset.

    Call :meth:`capture` to start accumulating :attr:`nFrames` frames
    with no illumination.  Once accumulated the mean is stored as the
    dark reference and :attr:`captured` is emitted.  Every subsequent
    frame is dark-subtracted; negative values are clipped to zero.

    Call :meth:`reset` to clear the stored reference.  Frames pass
    through unchanged until a new capture completes.

    If the incoming frame shape changes after capture the reference is
    incompatible; :meth:`get` returns the raw frame until a new
    capture is performed.

    Parameters
    ----------
    nFrames : int
        Number of frames to average during capture.  Default: ``16``.
    '''

    captured = QtCore.Signal()

    def __init__(self, nFrames: int = 16) -> None:
        super().__init__()
        self._dark: np.ndarray | None = None
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
        '''``True`` while a dark frame capture is in progress.'''
        return self._captureCount > 0

    def capture(self) -> None:
        '''Start accumulating a dark frame.

        Resets the accumulator and counts down :attr:`nFrames` calls
        to :meth:`add`.  :attr:`captured` is emitted on completion.
        '''
        self._accumulator = None
        self._captureCount = self._nFrames

    def reset(self) -> None:
        '''Clear the stored dark frame and any ongoing capture.

        Frames pass through unchanged until a new capture completes.
        '''
        self._dark = None
        self._accumulator = None
        self._captureCount = 0

    def add(self, image: Image) -> None:
        '''Incorporate a new frame into the filter state.

        During a capture, accumulates frames into a running sum.  When
        the target count is reached the mean is stored as the dark
        frame and :attr:`captured` is emitted.

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
                self._dark = (
                    self._accumulator / self._nFrames
                ).astype(np.uint8)
                self._accumulator = None
                self.captured.emit()
        self.data = image

    def get(self) -> Image | None:
        '''Return the dark-subtracted frame.

        Returns ``None`` before the first :meth:`add`, the raw frame
        if no dark reference is stored or if the frame shape does not
        match the reference, and the clipped dark-subtracted frame
        otherwise.

        Returns
        -------
        Image or None
        '''
        if self.data is None:
            return None
        if (self._dark is None
                or self.data.shape != self._dark.shape):
            return self.data
        return np.clip(
            self.data.astype(np.int16) - self._dark.astype(np.int16),
            0, 255).astype(np.uint8)


class QDarkFrameFilter(QVideoFilter):

    '''Widget for :class:`DarkFrameFilter` with capture controls.

    A checkable group box with a *frames* spinbox setting how many
    frames are averaged, a *Capture* button to start accumulation, and
    a *Reset* button to clear the stored dark frame.  The *Capture*
    button is disabled during accumulation and re-enabled on
    completion.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Dark Frame'
    display_category = 'Calibration'

    def __init__(
            self,
            parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Dark Frame', DarkFrameFilter())

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
    QDarkFrameFilter.example()
