#!/usr/bin/env python3
'''Demo combining a live video feed, camera controls, and a trackpy overlay.

Run directly::

    python -m QVideo.demos.trackpydemo

See :mod:`QVideo.overlays.trackpy` for literature references.
'''

from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree
from QVideo.overlays import QTrackpyWidget


__all__ = ['TrackpyDemo']


class TrackpyDemo(Demo):
    '''Extends :class:`~QVideo.demos.demo.Demo` with a trackpy overlay.

    Adds a :class:`~QVideo.overlays.trackpy.QTrackpyWidget` control panel
    below the camera control tree.  Detected particle positions are
    rendered in real time as a scatter-plot overlay on the video screen.

    Parameters
    ----------
    cameraTree : QCameraTree
        The camera control tree widget to display alongside the video feed.
    **kwargs :
        Additional keyword arguments forwarded to :class:`~QVideo.demos.demo.Demo`.
    '''

    def __init__(self, cameraTree: QCameraTree, **kwargs) -> None:
        super().__init__(cameraTree, **kwargs)
        self.trackpy = QTrackpyWidget(self)
        self.trackpy.source = self.screen.source
        self.screen.addOverlay(self.trackpy.overlay)
        self._controls.addWidget(self.trackpy)


def main() -> None:  # pragma: no cover
    '''Launch the trackpy demo with an interactively chosen camera.'''
    import sys
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    pg.mkQApp()
    camera = choose_camera().start()
    try:
        widget = TrackpyDemo(camera)
    except ImportError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
