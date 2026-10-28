#!/usr/bin/env python3
'''Camcorder with an interactive filter rack and three recording modes.

Run directly::

    python -m QVideo.demos.filterrackdemo

The filter rack starts with :class:`~QVideo.filters.smoothing.QSmoothingFilter`
and :class:`~QVideo.filters.threshold.QThresholdFilter` pre-loaded.
Additional filters can be added interactively via the "Add filter…" button,
and any filter can be removed or reordered by dragging.

One :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` runs the rack's
filters and feeds both the display and the recorder, so stateful filters
see each frame exactly once.  The three recording modes are:

**Raw**
    The unfiltered camera stream at the full camera frame rate.

**Filtered**
    The rack-processed stream from the pipeline, independent of the
    display throttle.  The pipeline works on its own thread and keeps a
    short queue of frames, so a brief slowdown does not lose frames.

**Display**
    The rack-processed stream at the throttled display rate.  Only
    frames that are actually rendered to screen are recorded.
'''

from qtpy import QtCore
from QVideo.QCamcorder import QCamcorder
from QVideo.dvr import QSourceSelector
from QVideo.lib import QFilterRack, launch
from QVideo.filters import QSmoothingFilter, QThresholdFilter


__all__ = ['FilterRackDemo']

#: Frames the filter pipeline may queue while its filters are busy.
_QUEUE_DEPTH = 8


class FilterRackDemo(QCamcorder):

    '''A camcorder whose frames pass through an editable filter rack.

    Data flow::

        camera -> filter pipeline -> screen
           |            |
           |            +--> recorder, in Filtered mode
           +---------------> recorder, in Raw mode
                    screen -> recorder, in Display mode

    Two extensions of :class:`~QVideo.QCamcorder.QCamcorder`, both in
    :meth:`_setupUi`: a :class:`~QVideo.lib.QFilterRack.QFilterRack`
    between the camera and the screen, and buttons that choose which stream
    the recorder saves (**Raw**, **Filtered** or **Display**).

    See :class:`~QVideo.QCamcorder.QCamcorder` for the parameters.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.rack = QFilterRack(self, source=self.source, depth=_QUEUE_DEPTH)
        self.rack.add(QSmoothingFilter())
        self.rack.add(QThresholdFilter())
        self.screen.source = self.rack.pipeline
        self.selector = QSourceSelector()
        self.selector.addSource('Raw', self.source)
        self.selector.addSource('Filtered', self.rack.pipeline)
        self.selector.addSource('Display', self.screen)
        self._controls.addWidget(self.selector)
        self._controls.addWidget(self.rack)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self.selector.sourceChanged.connect(self._setRecordingSource)
        self.dvr.recording.connect(self.selector.setDisabled)

    @QtCore.Slot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        '''Filter the DVR player instead of the camera during playback.

        The screen keeps displaying the filter pipeline, so playback frames
        pass through the rack exactly once and live camera frames never
        mix with them.

        Parameters
        ----------
        playback : bool
            ``True`` when DVR playback begins, ``False`` when it ends.
        '''
        played = self.dvr.playback.source
        self.rack.source = played if playback else self.source
        self.cameraWidget.setDisabled(playback)

    def _setRecordingSource(self, source) -> None:
        '''Record the stream that the selector chose.'''
        self.dvr.source = source


if __name__ == '__main__':  # pragma: no cover
    launch(FilterRackDemo, 'Filter Rack Demo')
