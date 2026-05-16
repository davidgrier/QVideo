'''Live illumination-uniformity widget.'''
from __future__ import annotations
from typing import TYPE_CHECKING
from qtpy import QtCore
import numpy as np
import pyqtgraph as pg

if TYPE_CHECKING:
    from QVideo.lib.QVideoScreen import QVideoScreen

__all__ = ['QUniformityWidget']


class QUniformityWidget(pg.GraphicsLayoutWidget):

    '''Live illumination-uniformity display.

    Shows mean pixel intensity as a function of x (averaged over y)
    and as a function of y (averaged over x), updating on every frame
    emitted by the connected
    :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.  Flat traces
    indicate uniform illumination; any slope, dip, or peak localises
    non-uniformity spatially.

    For colour images the mean is taken across channels before
    projecting, giving a single luminance profile per axis.

    Parameters
    ----------
    screen : QVideoScreen or None
        Video screen whose :attr:`newFrame` signal drives the display.
        May also be set later via :attr:`screen`.
    parent : QWidget or None
        Parent widget.
    '''

    def __init__(self,
                 screen: 'QVideoScreen | None' = None,
                 parent=None) -> None:
        super().__init__(parent=parent)
        self.setBackground('w')
        self._screen: 'QVideoScreen | None' = None
        self._setupUi()
        if screen is not None:
            self.screen = screen

    def _setupUi(self) -> None:
        pen = pg.mkPen('r', width=1)
        dark = pg.mkPen('k')
        label_style = {'color': '#000'}

        self._xplot = self.addPlot(row=0, col=0)
        self._xplot.setLabel('bottom', 'x (px)', **label_style)
        self._xplot.setLabel('left', 'Intensity', **label_style)
        self._xcurve = self._xplot.plot(pen=pen)

        self._yplot = self.addPlot(row=1, col=0)
        self._yplot.setLabel('bottom', 'y (px)', **label_style)
        self._yplot.setLabel('left', 'Intensity', **label_style)
        self._ycurve = self._yplot.plot(pen=pen)

        for plot in (self._xplot, self._yplot):
            for axis in ('bottom', 'left'):
                plot.getAxis(axis).setPen(dark)
                plot.getAxis(axis).setTextPen(dark)

    @property
    def screen(self) -> 'QVideoScreen | None':
        '''The connected :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.'''
        return self._screen

    @screen.setter
    def screen(self, screen: 'QVideoScreen') -> None:
        if self._screen is not None:
            self._screen.newFrame.disconnect(self.setFrame)
        self._screen = screen
        screen.newFrame.connect(self.setFrame)

    @QtCore.Slot(np.ndarray)
    def setFrame(self, image: np.ndarray) -> None:
        '''Compute and display the x- and y-intensity profiles.

        Parameters
        ----------
        image : numpy.ndarray
            Current video frame, shape ``(H, W)`` or ``(H, W, C)``.
        '''
        if image.ndim == 3:
            image = image.mean(axis=2)
        self._xcurve.setData(image.mean(axis=0))
        self._ycurve.setData(image.mean(axis=1))
