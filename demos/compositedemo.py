#!/usr/bin/env python3
'''Camcorder demo with a trackpy overlay and composite recording.

Run directly::

    python -m QVideo.demos.compositedemo

When the "Composite" checkbox is checked, the DVR records the rendered
scene (the video frame plus the trackpy particle markers) instead of the
raw camera frames.
'''

from qtpy import QtCore, QtWidgets
from QVideo.QCamcorder import QCamcorder
from QVideo.lib import launch
from QVideo.overlays import QTrackpyWidget


__all__ = ['CompositeDemo']


class CompositeDemo(QCamcorder):

    '''A camcorder that can record what the screen shows, markers included.

    Data flow::

        camera -> screen (+ trackpy markers)
           |         '--> recorder, when Composite is checked
           '----> trackpy detection
           '----> recorder, when it is not

    Two extensions of :class:`~QVideo.QCamcorder.QCamcorder`, both in
    :meth:`_setupUi`: a trackpy overlay that detects particles and marks
    them on the screen, and a checkbox that switches the recorder from the
    camera to the screen, whose ``composite`` flag makes it render the
    markers into the frames it emits.  See
    :class:`~QVideo.QCamcorder.QCamcorder` for the parameters.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.trackpy = QTrackpyWidget(self)
        self.trackpy.source = self.source
        self.screen.addOverlay(self.trackpy.overlay)
        self._compositeCheck = QtWidgets.QCheckBox('Composite')
        self._controls.addWidget(self.trackpy)
        self._controls.addWidget(self._compositeCheck)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._compositeCheck.toggled.connect(self._onCompositeToggled)

    @QtCore.Slot(bool)
    def _onCompositeToggled(self, checked: bool) -> None:
        '''Switch between raw and composite recording.

        Parameters
        ----------
        checked : bool
            ``True`` to record the rendered scene (video + overlay);
            ``False`` to record raw camera frames.
        '''
        self.screen.composite = checked
        self.dvr.source = self.screen if checked else self.source


if __name__ == '__main__':  # pragma: no cover
    launch(CompositeDemo, 'Composite Demo')
