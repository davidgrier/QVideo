#!/usr/bin/env python3
'''Camcorder that combines filters, a detection overlay and composite
recording.

Run directly::

    python -m QVideo.demos.combineddemo

This demo is a recipe for an application that uses several extensions at
once.  It adds one extension at a time to the demo before it:

1. :class:`~QVideo.QCamcorder.QCamcorder` supplies the screen, the camera
   controls and the recorder.
2. :class:`~QVideo.demos.filterrackdemo.FilterRackDemo` adds a filter
   pipeline: ``camera -> pipeline -> screen``.
3. :meth:`CombinedDemo._setupUi` adds the trackpy overlay.  It
   detects particles in the frames of the pipeline, so it sees what the
   screen shows.
4. The same method adds a recording mode that
   saves the rendered scene: the filtered video with the particle
   markers drawn on it.

Extensions that depend on each other, as the overlay depends on the
pipeline here, are combined by application code like this and not by the
framework, because only the application knows which stream each one needs.
'''

from QVideo.demos.filterrackdemo import FilterRackDemo
from QVideo.lib import launch
from QVideo.overlays import QTrackpyWidget


__all__ = ['CombinedDemo']


class CombinedDemo(FilterRackDemo):
    '''Camcorder with a filter rack, a trackpy overlay and four recording
    modes.

    Data flow::

        camera -> filter pipeline -> screen (+ trackpy markers)
                      |             |
                      |             +--> recorder, in Display or Composite
                      +--> trackpy detection
                      +--> recorder, in Filtered mode

    Extends :class:`~QVideo.demos.filterrackdemo.FilterRackDemo` with a
    :class:`~QVideo.overlays.trackpy.QTrackpyWidget` that locates
    particles in the filtered video, and a **Composite** recording mode
    in which the recorder saves the rendered scene (filtered video plus
    particle markers).

    See :class:`~QVideo.QCamcorder.QCamcorder` for the parameters.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.trackpy = QTrackpyWidget(self)
        self.trackpy.source = self.rack.pipeline
        self.screen.addOverlay(self.trackpy.overlay)
        self._controls.addWidget(self.trackpy)
        self.selector.addSource('Composite', self.screen)

    def _setRecordingSource(self, source) -> None:
        '''Render the overlay into the recording in Composite mode.'''
        self.screen.composite = self.selector.sourceName == 'Composite'
        super()._setRecordingSource(source)


if __name__ == '__main__':  # pragma: no cover
    launch(CombinedDemo, 'Combined Demo')
