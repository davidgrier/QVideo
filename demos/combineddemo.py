#!/usr/bin/env python3
'''Camcorder that combines filters, a detection overlay and composite
recording.

Run directly::

    python -m QVideo.demos.combineddemo

This demo is a recipe for an application that uses several extensions at
once.  It adds one extension at a time to the demo before it, and each
step is a short method of its own:

1. :class:`~QVideo.QCamcorder.QCamcorder` supplies the screen, the camera
   controls and the recorder.
2. :class:`~QVideo.demos.filterrackdemo.FilterRackDemo` adds a filter
   stack: ``camera -> stack -> screen``.
3. :meth:`CombinedDemo._setupOverlay` adds the trackpy overlay.  It
   detects particles in the frames of the stack, so it sees what the
   screen shows.
4. :meth:`CombinedDemo._setupCompositeMode` adds a recording mode that
   saves the rendered scene: the filtered video with the particle
   markers drawn on it.

Data flow::

    camera -> filter stack -> screen (+ trackpy markers)
                  |             |
                  |             +--> recorder, in Display or Composite mode
                  +--> trackpy detection
                  +--> recorder, in Filtered mode

Extensions that depend on each other, as the overlay depends on the
stack here, are combined by application code like this and not by the
framework, because only the application knows which stream each one needs.
'''

from qtpy import QtWidgets
from QVideo.demos.filterrackdemo import FilterRackDemo
from QVideo.lib import QCameraTree, launch
from QVideo.overlays import QTrackpyWidget


__all__ = ['CombinedDemo']


class CombinedDemo(FilterRackDemo):
    '''Camcorder with a filter rack, a trackpy overlay and four recording
    modes.

    Extends :class:`~QVideo.demos.filterrackdemo.FilterRackDemo` with a
    :class:`~QVideo.overlays.trackpy.QTrackpyWidget` that locates
    particles in the filtered video, and a **Composite** recording mode
    in which the recorder saves the rendered scene (filtered video plus
    particle markers).

    Parameters
    ----------
    cameraWidget : QCameraTree
        Camera control tree providing the video source.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~QVideo.demos.filterrackdemo.FilterRackDemo`.
    '''

    def __init__(self, cameraWidget: QCameraTree, **kwargs) -> None:
        super().__init__(cameraWidget, **kwargs)
        self._setupOverlay()
        self._setupCompositeMode()

    def _setupOverlay(self) -> None:
        '''Detect particles in the filtered stream and mark them on the
        screen.'''
        self.trackpy = QTrackpyWidget(self)
        self.trackpy.source = self.stack
        self.screen.addOverlay(self.trackpy.overlay)
        self.controls.layout().addWidget(self.trackpy)

    def _setupCompositeMode(self) -> None:
        '''Add the recording mode that saves the rendered scene.'''
        self._modeComposite = QtWidgets.QRadioButton('Composite')
        self._modeBox.layout().addWidget(self._modeComposite)
        self._modeGroup.addButton(self._modeComposite)

    def _onModeToggled(self,
                       button: QtWidgets.QAbstractButton,
                       checked: bool) -> None:
        '''Record the rendered scene in Composite mode, and the usual
        stream in the other modes.'''
        if checked:
            self.screen.composite = button is self._modeComposite
        super()._onModeToggled(button, checked)
        if checked and button is self._modeComposite:
            self.dvr.source = self.screen


if __name__ == '__main__':  # pragma: no cover
    launch(CombinedDemo, 'Combined Demo')
