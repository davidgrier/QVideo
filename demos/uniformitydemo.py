#!/usr/bin/env python3
'''Demo: illumination-uniformity plots beside the video.

Run directly::

    python -m QVideo.demos.uniformitydemo
'''

from QVideo.demos.demo import Demo
from QVideo.lib import launch
from QVideo.widgets import QUniformityWidget


__all__ = ['UniformityDemo']


class UniformityDemo(Demo):

    '''Plots of the mean intensity across the frames the screen displays.

    Data flow::

        camera -> screen -> uniformity plots

    The recipe is one widget that watches the screen:
    :class:`~QVideo.widgets.QUniformityWidget.QUniformityWidget`.  It shows the
    mean intensity as a function of x (averaged over y) and of y (averaged
    over x), updated on every displayed frame.  Flat traces mean uniform
    illumination; a slope, dip or peak locates the non-uniformity.  See
    :class:`~QVideo.demos.demo.Demo` for the parameters.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.uniformity = QUniformityWidget(self.screen)
        self._controls.addWidget(self.uniformity)


if __name__ == '__main__':  # pragma: no cover
    launch(UniformityDemo, 'Uniformity Demo')
