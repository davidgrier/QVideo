from qtpy import QtCore, QtWidgets
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from QVideo.lib.videotypes import Image


__all__ = ['RGBFilter', 'QRGBFilter']


class RGBFilter(VideoFilter):

    '''Extracts a single color channel from an RGB image.

    For grayscale (2-D) input the frame is passed through unchanged
    regardless of the :attr:`channel` setting.

    Parameters
    ----------
    channel : int
        Channel index to extract: ``0`` = Red, ``1`` = Green,
        ``2`` = Blue.  Default: ``0``.
    '''

    def __init__(self, channel: int = 0) -> None:
        super().__init__()
        self.channel = channel

    @property
    def channel(self) -> int:
        '''Channel index (0=Red, 1=Green, 2=Blue).'''
        return self._channel

    @channel.setter
    def channel(self, channel: int) -> None:
        if channel not in (0, 1, 2):
            raise ValueError(f'channel must be 0, 1, or 2; got {channel}')
        self._channel = channel

    def add(self, image: Image) -> None:
        '''Extract the selected channel and store the result.

        Parameters
        ----------
        image : Image
            Input frame.  2-D arrays are stored unchanged; 3-D arrays
            have the selected channel extracted.
        '''
        if image.ndim == 3:
            self.data = image[:, :, self._channel]
        else:
            self.data = image


class QRGBFilter(QVideoFilter):

    '''Widget for :class:`RGBFilter` with Red/Green/Blue radio buttons.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Color Channel', RGBFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        labels = ['Red', 'Green', 'Blue']
        self._buttons = [QtWidgets.QRadioButton(t) for t in labels]
        for n, button in enumerate(self._buttons):
            button.toggled.connect(lambda checked, n=n:
                                   self.setChannel(checked, n))
            self._layout.addWidget(button)
        self._buttons[self.filter.channel].setChecked(True)

    @QtCore.Slot(bool, int)
    def setChannel(self, checked: bool, channel: int) -> None:
        '''Set the active color channel.

        Called on every radio button toggle; only acts when *checked*
        is ``True`` to avoid updating the filter on the deselection
        signal of the previous button.

        Parameters
        ----------
        checked : bool
            Whether the button is being selected (``True``) or
            deselected (``False``).
        channel : int
            Channel index corresponding to the toggled button.
        '''
        if checked:
            self.filter.channel = channel


if __name__ == '__main__':  # pragma: no cover
    QRGBFilter.example()
