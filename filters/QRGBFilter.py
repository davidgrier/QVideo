from pyqtgraph.Qt.QtWidgets import (QWidget, QRadioButton)
from pyqtgraph.Qt.QtCore import pyqtSlot
from QVideo.lib.VideoFilter import (QVideoFilter, VideoFilter)
import numpy as np


__all__ = ['QRGBFilter', 'RGBFilter']


class QRGBFilter(QVideoFilter):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__('Color Channel', parent, RGBFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        labels = 'Red Green Blue'.split()
        buttons = [QRadioButton(t) for t in labels]
        for n, button in enumerate(buttons):
            self.layout.addWidget(button)
            button.toggled.connect(lambda c, n=n: self.setChannel(c, n))
        buttons[self.filter.channel].setChecked(True)

    @pyqtSlot(bool, int)
    def setChannel(self, checked: bool, channel: int) -> None:
        self.filter.channel = channel


class RGBFilter(VideoFilter):

    '''Extracts specified RGB channel from input image

    Properties
    ----------
    channel: int
        Channel to extract: 0=Red, 1=Green, 2=Blue

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

    def add(self, image: np.ndarray) -> None:
        '''Incorporates new data'''
        if image.ndim == 2:
            self.data = image
        else:
            self.data = np.squeeze(image[:, :, self.channel])

    def get(self) -> np.ndarray:
        '''Returns extracted channel image'''
        return self.data


if __name__ == '__main__':
    QRGBFilter.example()
