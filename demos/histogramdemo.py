#!/usr/bin/env python3
'''Demo: a live intensity histogram beside the video.

Run directly::

    python -m QVideo.demos.histogramdemo
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QHistogramWidget, launch


__all__ = ['HistogramDemo']


class HistogramDemo(Demo):

    '''A live intensity histogram of the frames the screen displays.

    Data flow::

        camera -> screen -> histogram
                     ^----------'  the level handles set the display range

    The recipe is one widget that watches the screen:
    :class:`~QVideo.lib.QHistogramWidget.QHistogramWidget`.  It updates on
    every displayed frame, and dragging its level handles changes the range
    that the screen displays.  See :class:`~QVideo.demos.demo.Demo` for the
    parameters.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.histogram = QHistogramWidget(self.screen)
        self._controls.addWidget(self.histogram)


if __name__ == '__main__':  # pragma: no cover
    launch(HistogramDemo, 'Histogram Demo')
