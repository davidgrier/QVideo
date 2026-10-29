'''Base classes for filters that correct frames with a stored reference.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
import numpy as np
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image


__all__ = ['ReferenceFilter', 'QReferenceFilter']


class ReferenceFilter(VideoFilter):

    '''A filter that corrects every frame with a reference that it captured.

    Dark-frame subtraction and flat-field division are two examples: the
    user covers the lens, or lights the sensor evenly, the filter averages
    :attr:`nFrames` frames into a reference, and every later frame is
    corrected with it.  This class does the capturing.  A subclass says
    what the reference is and how it corrects a frame, by implementing two
    methods:

    :meth:`_makeReference`
        Turn the average of the captured frames into the reference, or
        return ``None`` if the average cannot serve as one.
    :meth:`_correct`
        Return a frame that is corrected with the reference.

    Call :meth:`capture` to start averaging and :meth:`reset` to forget
    the reference.  Frames pass through unchanged until a capture
    completes, and when their shape differs from the reference's.

    Parameters
    ----------
    nFrames : int
        Number of frames to average during capture.  Default: ``16``.

    Signals
    -------
    captured()
        Emitted when a capture completes.

    Examples
    --------
    A bias frame, subtracted from every frame::

        class BiasFilter(ReferenceFilter):

            def _makeReference(self, mean):
                return mean

            def _correct(self, frame, reference):
                return np.clip(frame - reference, 0, 255).astype(np.uint8)
    '''

    #: Emitted when a reference has been captured.
    captured = QtCore.Signal()

    def __init__(self, nFrames: int = 16) -> None:
        super().__init__()
        self._reference: np.ndarray | None = None
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
        '''``True`` while a capture is in progress.'''
        return self._captureCount > 0

    @property
    def reference(self) -> np.ndarray | None:
        '''The stored reference, or ``None`` before the first capture.'''
        return self._reference

    def capture(self) -> None:
        '''Start averaging the next :attr:`nFrames` frames into a reference.

        The stored reference stays in force until the capture completes,
        and :attr:`captured` is emitted then.
        '''
        self._accumulator = None
        self._captureCount = self._nFrames

    def reset(self) -> None:
        '''Forget the reference and any capture in progress.

        Frames pass through unchanged until a new capture completes.
        '''
        self._reference = None
        self._accumulator = None
        self._captureCount = 0

    def add(self, image: Image) -> None:
        '''Take in a new frame, and average it into the reference if a
        capture is in progress.

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
                mean = self._accumulator / self._nFrames
                self._accumulator = None
                self._reference = self._makeReference(mean)
                self.captured.emit()
        self.data = image

    def get(self) -> Image | None:
        '''Return the corrected frame.

        Returns ``None`` before the first :meth:`add`, and the raw frame if
        there is no reference or if the frame does not have its shape.
        '''
        if self.data is None:
            return None
        if (self._reference is None
                or self.data.shape != self._reference.shape):
            return self.data
        return self._correct(self.data, self._reference)

    def _makeReference(self, mean: np.ndarray) -> np.ndarray | None:
        '''Return the reference for the average *mean* of the frames, or
        ``None`` if there is none.  Subclasses implement this.'''
        raise NotImplementedError

    def _correct(self, frame: Image, reference: np.ndarray) -> Image:
        '''Return *frame* corrected with *reference*.  Subclasses
        implement this.'''
        raise NotImplementedError


class QReferenceFilter(QVideoFilter):

    '''Widget of a :class:`ReferenceFilter`, with its capture controls.

    A checkable group box with a *frames* spinbox that sets how many
    frames are averaged, a *Capture* button that starts the capture and a
    *Reset* button that forgets the reference.  *Capture* is disabled
    while frames are being averaged.

    A subclass sets :attr:`display_name`, which is also the title of the
    box, and :attr:`filterClass`::

        class QBiasFilter(QReferenceFilter):
            display_name = 'Bias'
            filterClass = BiasFilter

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.

    Class Attributes
    ----------------
    filterClass : type
        The :class:`ReferenceFilter` that the widget makes and controls.
    display_category : str
        Defaults to ``'Calibration'``.
    '''

    display_category = 'Calibration'
    filterClass: type[ReferenceFilter] = ReferenceFilter

    def __init__(self,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, self.display_name, self.filterClass())

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
