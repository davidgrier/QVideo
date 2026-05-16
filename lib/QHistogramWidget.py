'''Live pixel-intensity histogram widget.'''
from __future__ import annotations
from typing import TYPE_CHECKING
import pyqtgraph as pg

if TYPE_CHECKING:
    from QVideo.lib.QVideoScreen import QVideoScreen

__all__ = ['QHistogramWidget']


class QHistogramWidget(pg.HistogramLUTWidget):

    '''Live pixel-intensity histogram with adjustable display levels.

    Wraps :class:`pyqtgraph.HistogramLUTWidget` and links it to a
    :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.  The histogram
    updates automatically on every displayed frame via the
    :class:`~pyqtgraph.ImageItem`\'s ``sigImageChanged`` signal.
    The draggable level handles let the user set the minimum and
    maximum intensity values mapped to the display range; those
    levels are fed back to the connected
    :class:`~pyqtgraph.ImageItem` immediately.

    Parameters
    ----------
    screen : QVideoScreen or None
        Video screen to connect.  May also be set later via
        :attr:`screen`.
    parent : QWidget or None
        Parent widget.
    '''

    def __init__(self,
                 screen: 'QVideoScreen | None' = None,
                 parent=None) -> None:
        super().__init__(parent=parent, background='w')
        self._screen: 'QVideoScreen | None' = None
        self.item.plot.setPen(pg.mkPen('k', width=1))
        self.item.axis.setPen(pg.mkPen('k'))
        self.item.axis.setTextPen(pg.mkPen('k'))
        gradient = self.item.gradient
        gradient.tickPen = pg.mkPen('k')
        for tick in gradient.ticks:
            tick.pen = tick.currentPen = pg.mkPen('k')
            tick.update()
        if screen is not None:
            self.screen = screen

    @property
    def screen(self) -> 'QVideoScreen | None':
        '''The connected :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.'''
        return self._screen

    @screen.setter
    def screen(self, screen: 'QVideoScreen') -> None:
        self._screen = screen
        self.setImageItem(screen.image)
        self.setLevels(0, 255)
