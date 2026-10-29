'''Finished widgets that an application places beside the video.

Each shows or measures what a :class:`~QVideo.lib.QVideoScreen.QVideoScreen`
displays, or helps to lay out a window; none is a base class.

Classes
-------
QHistogramWidget
    Live histogram of the pixel intensities on a screen.
QUniformityWidget
    Mean intensity along x and along y, to check the illumination.
QScrollPanel
    A panel of controls that scrolls when the window is too short.
QCameraChooser
    A combo box of the cameras that work.
'''
from .QHistogramWidget import QHistogramWidget
from .QUniformityWidget import QUniformityWidget
from .QScrollPanel import QScrollPanel
from .QCameraChooser import QCameraChooser

__all__ = ['QHistogramWidget', 'QUniformityWidget', 'QScrollPanel',
           'QCameraChooser']
