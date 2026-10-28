#!/usr/bin/env python3
'''Camcorder demo with a trackpy overlay and composite recording.

Run directly::

    python -m QVideo.demos.compositedemo

When "Composite" is selected under "Record from", the DVR records the rendered
scene (the video frame plus the trackpy particle markers) instead of the
raw camera frames.
'''

from QVideo.QCamcorder import QCamcorder
from QVideo.dvr import QSourceSelector
from QVideo.lib import launch
from QVideo.overlays import QTrackpyWidget


__all__ = ['CompositeDemo']


class CompositeDemo(QCamcorder):

    '''A camcorder that can record what the screen shows, markers included.

    Data flow::

        camera -> screen (+ trackpy markers)
           |         '--> recorder, when Composite is selected
           '----> trackpy detection
           '----> recorder, when Raw is selected

    Two extensions of :class:`~QVideo.QCamcorder.QCamcorder`, both in
    :meth:`_setupUi`: a trackpy overlay that detects particles and marks
    them on the screen, and a selector that switches the recorder from the
    camera to the screen, whose ``composite`` flag makes it render the
    markers into the frames it emits.  See
    :class:`~QVideo.QCamcorder.QCamcorder` for the parameters.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.trackpy = QTrackpyWidget(self)
        self.trackpy.source = self.source
        self.screen.addOverlay(self.trackpy.overlay)
        self.selector = QSourceSelector()
        self.selector.addSource('Raw', self.source)
        self.selector.addSource('Composite', self.screen)
        self._controls.addWidget(self.trackpy)
        self._controls.addWidget(self.selector)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self.selector.sourceChanged.connect(self._setRecordingSource)
        self.dvr.recording.connect(self.selector.setDisabled)

    def _setRecordingSource(self, source) -> None:
        '''Render the overlay into the recording in Composite mode.'''
        self.screen.composite = source is self.screen
        self.dvr.source = source


if __name__ == '__main__':  # pragma: no cover
    launch(CompositeDemo, 'Composite Demo')
