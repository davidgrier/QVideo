from pyqtgraph.Qt.QtWidgets import (QWidget, QHBoxLayout, QRadioButton)
from pyqtgraph.Qt.QtCore import pyqtSlot
from QVideo.lib.VideoFilter import VideoFilter
import numpy as np


__all__ = ['QRGBFilter', 'RGBFilter']


class QRGBFilter(QWidget):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.filter = RGBFilter()
        self._setupUi()

    def __call__(self, image: np.ndarray) -> RGBFilter:
        return self.filter(image)

    def _setupUi(self) -> None:
        layout = QHBoxLayout(self)
        labels = 'Red Green Blue All'.split()
        buttons = [QRadioButton(t) for t in labels]
        buttons[3].setChecked(True)
        for n, button in enumerate(buttons):
            layout.addWidget(button)
            button.toggled.connect(lambda c, n=n: self.setChannel(c, n))

    @pyqtSlot(bool, int)
    def setChannel(self, checked: bool, channel: int) -> None:
        if checked:
            self.filter.channel = channel


class RGBFilter(VideoFilter):

    '''Extracts specified RGB channel from input image

    Properties
    ----------
    channel: int
        Channel to extract: 0=Red, 1=Green, 2=Blue
        Default: 3 (passes through all channels)

    Methods
    -------
    add(data: np.ndarray): None
        Incorporates new image data.
    get(): np.ndarray
        Returns extracted channel image.
    '''

    def __init__(self, channel: int = 0) -> None:
        super().__init__()
        self.channel = channel

    def add(self, data: np.ndarray) -> None:
        '''Incorporates new data'''
        self.data = data
        self.passthrough = (self.channel == 3) or (data.ndim < 3)

    def get(self) -> np.ndarray:
        '''Returns extracted channel image'''
        if self.passthrough:
            return self.data
        return np.squeeze(self.data[:, :, self.channel])


def example() -> None:
    import pyqtgraph as pg

    app = pg.mkQApp()
    widget = QRGBFilter()
    widget.show()
    pg.exec()


if __name__ == '__main__':
    example()
