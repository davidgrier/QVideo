from pyqtgraph.Qt import QtCore, QtWidgets
from QVideo.lib.VideoFilter import QVideoFilter
from QVideo.lib.types import Image
from QVideo.filters.Normalize import Normalize


__all__ = ['SampleHold', 'QSampleHold']


class SampleHold(Normalize):

    '''Normalize an image against a sampled background estimate.

    Accumulates ``3 ** order`` frames into the running-median background
    estimator inherited from :class:`~QVideo.filters.Normalize.Normalize`,
    then holds that estimate fixed.  Subsequent frames are normalized
    against the held background.  Calling :meth:`reset` restarts the
    accumulation, allowing the background to be refreshed on demand.

    When the frame shape changes the accumulation is automatically
    restarted.

    Parameters
    ----------
    *args :
        Positional arguments forwarded to :class:`Normalize`.
    **kwargs :
        Keyword arguments forwarded to :class:`Normalize`
        (``order``, ``scale``, ``mean``, ``darkcount``).

    Notes
    -----
    This filter is designed to be used via :class:`QSampleHold`, which
    provides a *Reset* button to trigger :meth:`reset` interactively.
    '''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.reset()

    def reset(self) -> None:
        '''Restart background accumulation.

        Resets the frame counter so that the next ``3 ** order`` frames
        are used to build a fresh background estimate.
        '''
        self.count = 3 ** self.order

    def add(self, image: Image) -> None:
        '''Incorporate a new frame into the filter state.

        While the frame counter is positive the frame is passed to the
        parent :class:`Normalize` accumulator to build the background
        estimate.  Once the counter reaches zero the frame is stored as
        the foreground (normalized against the held background).

        If the frame shape changes :meth:`reset` is called automatically.

        Parameters
        ----------
        image : Image
            Input frame.
        '''
        if image.shape != self.shape:
            self.reset()
        if self.count > 0:
            super().add(image)
            self.count -= 1
        else:
            self._fg = image - self.darkcount


class QSampleHold(QVideoFilter):

    '''Widget for :class:`SampleHold` with a *Reset* button.

    Wraps :class:`SampleHold` in a checkable group box.  The *Reset*
    button triggers :meth:`~SampleHold.reset`, causing the filter to
    re-sample the background on the next ``3 ** order`` frames.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__('Sample and Hold', parent, SampleHold())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._reset_button = QtWidgets.QPushButton('Reset', self)
        self._reset_button.clicked.connect(self.reset)
        self.layout.addWidget(self._reset_button)

    @QtCore.pyqtSlot(bool)
    def reset(self, _checked: bool = False) -> None:
        '''Reset the background estimate.

        Connected to the *Reset* button.  The *_checked* argument is the
        toggle state emitted by :class:`~pyqtgraph.Qt.QtWidgets.QPushButton`
        and is ignored.

        Parameters
        ----------
        _checked : bool
            Unused toggle state from the button signal.
        '''
        self.filter.reset()


if __name__ == '__main__':  # pragma: no cover
    QSampleHold.example()
