'''The splash screen that a camera application shows while it starts.'''
from importlib.metadata import PackageNotFoundError, version
import numpy as np
from qtpy import QtCore, QtGui, QtWidgets


__all__ = ['splash', 'say']

try:
    _VERSION = version('QVideo')
except PackageNotFoundError:  # pragma: no cover
    _VERSION = ''

#: Size of the image on the screen; it is drawn at twice this size, so
#: that it is sharp on high-resolution displays.
_SIZE = (480, 240)
#: Where the particle is, as a fraction of the size: upper left.
_CENTER = (0.31, 0.31)
#: Contrast of the fringes: low, so that the text stays legible.
_CONTRAST = 0.7
#: NYU purple.
_PURPLE = np.array([87, 6, 140]) / 255.


def _hologram(width: int, height: int) -> QtGui.QImage:
    '''Return the fringes of a particle that scatters light, in purple.

    Far from a small particle the fringes are the zones of a Fresnel
    lens: rings that crowd together and fade with distance.  A vignette
    darkens the corners.
    '''
    y, x = np.mgrid[:height, :width]
    r = np.hypot(x - _CENTER[0] * width, y - _CENTER[1] * height) / width
    fringes = 1. + np.cos(2 * np.pi * (60. * r**2 + 5. * r)) / (1. + 12. * r)
    edge = np.hypot(x / width - 0.5, y / height - 0.5)
    brightness = (1. + _CONTRAST * (fringes - 1.)) * (1. - 0.8 * edge**2)
    rgb = np.clip(_PURPLE * brightness[..., None] * 1.15, 0., 1.)
    pixels = np.ascontiguousarray(255 * rgb, dtype=np.uint8)
    image = QtGui.QImage(pixels.data, width, height, 3 * width,
                         QtGui.QImage.Format.Format_RGB888)
    return image.copy()  # the copy owns its pixels


def splash(title: str | None = None) -> QtWidgets.QSplashScreen:
    '''Return a splash screen with the fringes, *title* and the version.'''
    width, height = (2 * n for n in _SIZE)
    pixmap = QtGui.QPixmap.fromImage(_hologram(width, height))
    pixmap.setDevicePixelRatio(2.)
    align = QtCore.Qt.AlignmentFlag
    painter = QtGui.QPainter(pixmap)
    painter.setPen(QtGui.QColor('white'))
    font = QtGui.QFont()
    font.setPointSize(30)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(0, 0, _SIZE[0] - 16, _SIZE[1] - 46,
                     align.AlignRight | align.AlignBottom, title or 'QVideo')
    font.setPointSize(11)
    font.setBold(False)
    painter.setFont(font)
    painter.drawText(0, 0, _SIZE[0] - 16, _SIZE[1] - 28,
                     align.AlignRight | align.AlignBottom,
                     f'QVideo {_VERSION}')
    painter.end()
    screen = QtWidgets.QSplashScreen(pixmap)
    screen.setFont(QtGui.QFont(screen.font().family(), 10))
    return screen


def say(screen: QtWidgets.QSplashScreen, message: str) -> None:
    '''Show *message* on *screen* and repaint before the next slow step.'''
    align = QtCore.Qt.AlignmentFlag
    screen.showMessage(message, align.AlignBottom | align.AlignRight,
                       QtGui.QColor('#d9b8f0'))
    QtWidgets.QApplication.processEvents()
