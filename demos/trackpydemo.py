#!/usr/bin/env python3
'''Demo: particle detection with trackpy, drawn over the video.

Run directly::

    python -m QVideo.demos.trackpydemo

See :mod:`QVideo.overlays.trackpy` for literature references.
'''

from QVideo.demos.demo import Demo
from QVideo.lib import launch
from QVideo.overlays import QTrackpyWidget


__all__ = ['TrackpyDemo']


class TrackpyDemo(Demo):

    '''Detected particles marked on the live video.

    Data flow::

        camera -> screen
           '----> trackpy (worker thread) -> markers on the screen

    The recipe is a detector that listens to the camera and an overlay
    that the screen draws: :class:`~QVideo.overlays.trackpy.QTrackpyWidget`
    holds the controls, and its ``overlay`` is the scatter plot of
    positions.  Detection runs on a thread of its own, so a slow frame
    never delays the display.  See :class:`~QVideo.demos.demo.Demo` for the
    parameters.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.trackpy = QTrackpyWidget(self)
        self.trackpy.source = self.cameraTree.source
        self.screen.addOverlay(self.trackpy.overlay)
        self._controls.addWidget(self.trackpy)


if __name__ == '__main__':  # pragma: no cover
    launch(TrackpyDemo, 'Trackpy Demo')
