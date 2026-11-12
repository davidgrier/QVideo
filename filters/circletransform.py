'''Orientation alignment transform filter — detects ring-like features.'''
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image
from QVideo.lib.imageops import grayscale
import cv2
import numpy as np
from numpy.typing import NDArray


__all__ = ['CircleTransformFilter', 'QCircleTransformFilter']


def _dgimage():
    '''Import dgimage, an optional dependency, when a filter is created.'''
    try:
        import dgimage
    except ImportError as error:
        raise ImportError(
            'CircleTransformFilter requires dgimage: '
            'pip install "QVideo[circletransform]"') from error
    return dgimage


class CircleTransformFilter(VideoFilter):

    '''Orientation alignment transform (OAT) ring-detection filter.

    Detects circularly symmetric ring-like features by computing the
    orientation alignment transform of Krishnatreya & Grier (2014), which
    :func:`dgimage.circletransform` implements for QVideo, pylorenzmie and
    other projects.  The computation is heavy, so run the filter in a
    :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline`, which keeps it off
    the GUI thread.

    The filter is made for a live display and uses the fast options of
    dgimage by default: single precision (1.7 times faster, a difference of
    3e-7 of the peak) and a binning of 2 (the transform of the frame
    averaged in blocks of 2 by 2 pixels: 2.3 times faster in all, and a
    smoother map in which a sphere is one blob).  Together they take about
    6 ms for a frame of 1280 by 1024, against 30 ms for the filter that
    carried its own double precision copy of the transform.  The map is
    scaled back to the size of the frame, so that positions in it are those
    of the frame.  Set ``binning=1`` for the map
    at full resolution (the highest pixel of a blob, which is scattered over
    the blob at full resolution, is then not the same pixel).

    Parameters
    ----------
    window : int
        Savitzky-Golay derivative window size [pixels] of the binned image.
        Must be odd and greater than *polyorder*.  Larger values smooth noise
        but reduce spatial resolution of detected ring centers.
        Default: ``13``.
    polyorder : int
        Savitzky-Golay polynomial order.  Must be less than *window*.
        Default: ``3``.
    binning : int
        Average blocks of *binning* by *binning* pixels first.  ``1`` is no
        binning.  Default: ``2``.

    Notes
    -----
    The output is normalized per-frame so that its peak is white, and
    peak brightness indicates likely ring centers.  A ``uint8`` frame gives
    a ``uint8`` map between 0 and 255.  The filter is ``deep``: a ``uint16``
    frame of a camera of more than 8 bits goes in as it is, so that the
    gradients use all of its bits, and the map is ``uint16`` between the
    black and white levels of the frame, which keeps the scale that the
    screen and the recorder expect.

    References
    ----------
    B. J. Krishnatreya and D. G. Grier,
    'Fast feature identification for holographic tracking: the
    orientation alignment transform,'
    *Optics Express* **22**, 12773–12778 (2014).
    '''

    deep = True

    def __init__(self, window: int = 13, polyorder: int = 3,
                 binning: int = 2) -> None:
        self._transform = _dgimage().CircleTransform(
            window, polyorder, dtype=np.float32, binning=binning)
        super().__init__()

    @property
    def window(self) -> int:
        '''Savitzky-Golay derivative window [pixels], always odd and ≥ 3.'''
        return self._transform.window

    @window.setter
    def window(self, window: int) -> None:
        self._transform.window = window

    @property
    def polyorder(self) -> int:
        '''Savitzky-Golay polynomial order, always ≥ 1.'''
        return self._transform.polyorder

    @polyorder.setter
    def polyorder(self, polyorder: int) -> None:
        self._transform.polyorder = polyorder

    @property
    def binning(self) -> int:
        '''Size of the blocks that are averaged first, always ≥ 1.'''
        return self._transform.binning

    @binning.setter
    def binning(self, binning: int) -> None:
        self._transform.binning = binning

    def _heat(self, gray: Image) -> NDArray[np.floating]:
        '''The map of *gray*, between 0 and 1, of the shape of *gray*.'''
        heat = self._transform.transform(gray)
        if heat.shape == gray.shape:
            return heat
        ny, nx = (n * self.binning for n in heat.shape)
        up = cv2.resize(heat, (nx, ny), interpolation=cv2.INTER_LINEAR)
        up = np.pad(up, ((0, gray.shape[0] - ny), (0, gray.shape[1] - nx)),
                    mode='edge')            # rows that did not fill a block
        peak = up.max()
        if peak > np.finfo(np.float32).eps:
            up /= peak                      # the peak stays white
        return up

    def process(self, image: Image) -> Image:
        '''Compute the OAT of *image* and return a heat map.

        Parameters
        ----------
        image : Image
            Input frame: grayscale or color ``uint8``, or grayscale
            ``uint16`` (a deep frame).

        Returns
        -------
        Image
            OAT heat map, same spatial shape and dtype as *image* (a color
            frame gives ``uint8``).  Bright peaks indicate ring centers.
        '''
        gray = grayscale(image)
        heat = self._heat(gray)
        if gray.dtype == np.uint16:
            black, white = self.bounds(image)
            return np.round(black + heat * (white - black)).clip(
                black, white).astype(np.uint16)
        return np.round(heat * 255.).clip(0, 255).astype(np.uint8)


class QCircleTransformFilter(QVideoFilter):

    '''Widget for :class:`CircleTransformFilter` with a window spinbox and
    one for the binning (1 turns it off).

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    display_name = 'Circle Transform'
    display_category = 'Feature Detection'

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Circle Transform', CircleTransformFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._layout.addWidget(QtWidgets.QLabel('window'))
        self._spinbox = SpinBox(value=self.videoFilter.window,
                                step=2, int=True)
        self._spinbox.setMinimum(3)
        self._layout.addWidget(self._spinbox)
        self._layout.addWidget(QtWidgets.QLabel('bin'))
        self._binbox = SpinBox(value=self.videoFilter.binning,
                               step=1, int=True, bounds=(1, 8))
        self._layout.addWidget(self._binbox)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._spinbox.valueChanged.connect(self._setWindow)
        self._binbox.valueChanged.connect(self._setBinning)

    @QtCore.Slot(object)
    def _setWindow(self, window: int) -> None:
        self.videoFilter.window = window
        with QtCore.QSignalBlocker(self._spinbox):
            self._spinbox.setValue(self.videoFilter.window)

    @QtCore.Slot(object)
    def _setBinning(self, binning: int) -> None:
        self.videoFilter.binning = binning
        with QtCore.QSignalBlocker(self._binbox):
            self._binbox.setValue(self.videoFilter.binning)


if __name__ == '__main__':  # pragma: no cover
    QCircleTransformFilter.example()
