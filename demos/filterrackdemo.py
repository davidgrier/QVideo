#!/usr/bin/env python3
'''Camcorder with an interactive filter rack and three recording modes.

Run directly::

    python -m QVideo.demos.filterrackdemo

The filter rack starts with :class:`~QVideo.filters.smoothing.QSmoothingFilter`
and :class:`~QVideo.filters.threshold.QThresholdFilter` pre-loaded.
Additional filters can be added interactively via the "Add filter…" button,
and any filter can be removed or reordered by dragging.

Three recording modes are offered:

**Raw**
    The unfiltered camera stream at the full camera frame rate.

**Filtered**
    The rack-processed stream from the filter pipeline, independent of the
    display throttle.  The pipeline works on its own thread and keeps a
    short queue of frames, so a brief slowdown does not lose frames.

**Display**
    The rack-processed stream at the throttled display rate.  Only
    frames that are actually rendered to screen are recorded.

One :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` runs the rack's
filters and feeds both the display and the recorder, so stateful filters
see each frame exactly once.
'''

from qtpy import QtCore, QtWidgets
from QVideo.QCamcorder import QCamcorder
from QVideo.lib import QCameraTree, QFilterRack, launch
from QVideo.filters import QSmoothingFilter, QThresholdFilter


__all__ = ['FilterRackDemo']

#: Frames the filter pipeline may queue while its filters are busy.
_QUEUE_DEPTH = 8


class FilterRackDemo(QCamcorder):
    '''Camcorder with an interactive filter rack and three recording modes.

    Extends :class:`~QVideo.QCamcorder.QCamcorder` by adding a
    :class:`~QVideo.lib.QFilterRack.QFilterRack` pre-loaded with
    :class:`~QVideo.filters.smoothing.QSmoothingFilter` and
    :class:`~QVideo.filters.threshold.QThresholdFilter`, and
    a group of radio buttons to select the DVR recording source:

    - **Raw**: unfiltered frames at the camera's full frame rate.
    - **Filtered**: rack-processed frames from the filter pipeline.
    - **Display**: rack-processed frames at the throttled display rate.

    Parameters
    ----------
    cameraWidget : QCameraTree
        Camera control tree providing the video source.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~QVideo.QCamcorder.QCamcorder`.
    '''

    def __init__(self, cameraWidget: QCameraTree, **kwargs) -> None:
        super().__init__(cameraWidget, **kwargs)
        self.rack = QFilterRack(self, depth=_QUEUE_DEPTH)
        self.rack.source = self.source
        self.screen.source = self.rack.pipeline
        self._setupModeUi()
        self._connectModeSignals()
        self.controls.layout().addWidget(self._modeBox)
        self.controls.layout().addWidget(self.rack)
        self.rack.add(QSmoothingFilter())
        self.rack.add(QThresholdFilter())

    def _setupModeUi(self) -> None:
        self._modeBox = QtWidgets.QGroupBox('Record from')
        layout = QtWidgets.QHBoxLayout(self._modeBox)
        self._modeRaw = QtWidgets.QRadioButton('Raw')
        self._modeFiltered = QtWidgets.QRadioButton('Filtered')
        self._modeDisplay = QtWidgets.QRadioButton('Display')
        self._modeRaw.setChecked(True)
        for btn in (self._modeRaw, self._modeFiltered, self._modeDisplay):
            layout.addWidget(btn)
        self._modeGroup = QtWidgets.QButtonGroup(self)
        self._modeGroup.addButton(self._modeRaw)
        self._modeGroup.addButton(self._modeFiltered)
        self._modeGroup.addButton(self._modeDisplay)
        self._sources = {self._modeRaw: self.source,
                         self._modeFiltered: self.rack.pipeline,
                         self._modeDisplay: self.screen}

    def _connectModeSignals(self) -> None:
        self._modeGroup.buttonToggled.connect(self._onModeToggled)

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
        self.rack.source = self.dvr.player if playback else self.source
        self.cameraWidget.setDisabled(playback)

    @QtCore.Slot(QtWidgets.QAbstractButton, bool)
    def _onModeToggled(self,
                       button: QtWidgets.QAbstractButton,
                       checked: bool) -> None:
        '''Switch the DVR source when a recording-mode button is selected.

        Parameters
        ----------
        button : QAbstractButton
            The button whose state changed.
        checked : bool
            ``True`` when the button is selected; ``False`` on deselection.
        '''
        if checked:
            self.dvr.source = self._sources[button]


if __name__ == '__main__':  # pragma: no cover
    launch(FilterRackDemo, 'Filter Rack Demo')
