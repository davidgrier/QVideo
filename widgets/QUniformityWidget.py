'''Live illumination-uniformity widget.'''
from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar
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
    indicate uniform illumination; any slope, dip, or peak localizes
    non-uniformity spatially.

    A gray image has one trace per axis.  A color image has three,
    red, green and blue, so that a color cast in the illumination shows
    up as traces that differ.  (An image with an alpha channel is
    plotted without it.)

    Parameters
    ----------
    screen : QVideoScreen or None
        Video screen whose :attr:`newFrame` signal drives the display.
        May also be set later via :attr:`screen`.
    parent : QWidget or None
        Parent widget.
    '''

    COLORS: ClassVar[tuple[str, ...]] = ('r', 'g', 'b')

    def __init__(self,
                 screen: QVideoScreen | None = None,
                 parent=None) -> None:
        super().__init__(parent=parent)
        self.setBackground('w')
        self._screen: QVideoScreen | None = None
        self._setupUi()
        if screen is not None:
            self.screen = screen

    def _setupUi(self) -> None:
        dark = pg.mkPen('k')
        label_style = {'color': '#000'}

        self._xplot = self.addPlot(row=0, col=0)
        self._xplot.setLabel('bottom', 'x (px)', **label_style)
        self._yplot = self.addPlot(row=1, col=0)
        self._yplot.setLabel('bottom', 'y (px)', **label_style)
        for plot in (self._xplot, self._yplot):
            plot.setLabel('left', 'Intensity', **label_style)
            for axis in ('bottom', 'left'):
                plot.getAxis(axis).setPen(dark)
                plot.getAxis(axis).setTextPen(dark)

        # the trace of a gray image, and the three of a color image
        self._xcurve = self._xplot.plot(pen=pg.mkPen('k', width=1))
        self._ycurve = self._yplot.plot(pen=pg.mkPen('k', width=1))
        self._xcolor = [self._xplot.plot(pen=pg.mkPen(c, width=1))
                        for c in self.COLORS]
        self._ycolor = [self._yplot.plot(pen=pg.mkPen(c, width=1))
                        for c in self.COLORS]
        self._showColor(False)

    def _showColor(self, color: bool) -> None:
        self._xcurve.setVisible(not color)
        self._ycurve.setVisible(not color)
        for curve in (*self._xcolor, *self._ycolor):
            curve.setVisible(color)

    @property
    def screen(self) -> QVideoScreen | None:
        '''The connected :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.'''
        return self._screen

    @screen.setter
    def screen(self, screen: QVideoScreen) -> None:
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
            A color frame is plotted as its first three channels (red,
            green and blue).
        '''
        color = image.ndim == 3
        self._showColor(color)
        if not color:
            self._xcurve.setData(image.mean(axis=0))
            self._ycurve.setData(image.mean(axis=1))
            return
        for c, (xc, yc) in enumerate(zip(self._xcolor, self._ycolor,
                                         strict=True)):
            xc.setData(image[:, :, c].mean(axis=0))
            yc.setData(image[:, :, c].mean(axis=1))
