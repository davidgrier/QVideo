'''Sample-and-hold background normalisation filter and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from QVideo.filters.Normalize import Normalize
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image


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
        self._count = 3 ** self.order

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
        if self._count > 0:
            super().add(image)
            self._count -= 1
        else:
            self._fg = image - self.darkcount


class QSampleHold(QVideoFilter):

    '''Widget for :class:`SampleHold` with order buttons and a *Reset* button.

    Wraps :class:`SampleHold` in a checkable group box.  Three radio
    buttons select the accumulation order (1, 2, or 3), corresponding
    to background estimates built from 3, 9, or 27 frames respectively.
    The *Reset* button triggers :meth:`~SampleHold.reset`, causing the
    filter to re-sample the background using the selected order.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Sample and Hold', SampleHold())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._layout.addWidget(QtWidgets.QLabel('order'))
        self._orderButtons = [
            QtWidgets.QRadioButton(str(n)) for n in (1, 2, 3)]
        for n, button in enumerate(self._orderButtons, start=1):
            button.toggled.connect(
                lambda checked, n=n: self.setOrder(checked, n))
            self._layout.addWidget(button)
        self._orderButtons[self.filter.order - 1].setChecked(True)
        self._resetButton = QtWidgets.QPushButton('Reset', self)
        self._resetButton.clicked.connect(self.reset)
        self._layout.addWidget(self._resetButton)

    @QtCore.Slot(bool, int)
    def setOrder(self, checked: bool, order: int) -> None:
        '''Set the accumulation order and restart background sampling.

        Only acts when *checked* is ``True`` to avoid double-firing on
        radio button deselection.  Setting a new order clears the
        estimator and restarts accumulation immediately.

        Parameters
        ----------
        checked : bool
            Whether the button is being selected (``True``) or
            deselected (``False``).
        order : int
            Accumulation order (1, 2, or 3).
        '''
        if checked:
            self.filter.order = order
            self.filter.reset()

    @QtCore.Slot(bool)
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
