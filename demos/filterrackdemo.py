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
    The rack-processed stream from the filter stack, independent of the
    display throttle.  The stack works on its own thread and keeps a
    short queue of frames, so a brief slowdown does not lose frames.

**Display**
    The rack-processed stream at the throttled display rate.  Only
    frames that are actually rendered to screen are recorded.

One :class:`~QVideo.lib.QFilterStack.QFilterStack` runs the rack's
filters and feeds both the display and the recorder, so stateful filters
see each frame exactly once.
'''

from qtpy import QtCore, QtGui, QtWidgets
from QVideo.QCamcorder import QCamcorder
from QVideo.lib import QCameraTree, QFilterRack, QFilterStack
from QVideo.filters import QSmoothingFilter, QThresholdFilter


__all__ = ['FilterRackDemo']

#: Frames the filter stack may queue while its filters are busy.
_QUEUE_DEPTH = 8


class FilterRackDemo(QCamcorder):
    '''Camcorder with an interactive filter rack and three recording modes.

    Extends :class:`~QVideo.QCamcorder.QCamcorder` by adding a
    :class:`~QVideo.lib.QFilterRack.QFilterRack` pre-loaded with
    :class:`~QVideo.filters.smoothing.QSmoothingFilter` and
    :class:`~QVideo.filters.threshold.QThresholdFilter`, and
    a group of radio buttons to select the DVR recording source:

    - **Raw**: unfiltered frames at the camera's full frame rate.
    - **Filtered**: rack-processed frames from the filter stack.
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
        self.rack = QFilterRack(self)
        self.rack.add(QSmoothingFilter())
        self.rack.add(QThresholdFilter())
        self.stack = QFilterStack(self.source, rack=self.rack,
                                  depth=_QUEUE_DEPTH, parent=self)
        self.screen.source = self.stack
        self._setupModeUi()
        self._connectModeSignals()
        self.controls.layout().addWidget(self._modeBox)
        self.controls.layout().addWidget(self.rack)

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

    def _connectModeSignals(self) -> None:
        self._modeGroup.buttonToggled.connect(self._onModeToggled)

    @QtCore.Slot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        '''Filter the DVR player instead of the camera during playback.

        The screen keeps displaying the filter stack, so playback frames
        pass through the rack exactly once and live camera frames never
        mix with them.

        Parameters
        ----------
        playback : bool
            ``True`` when DVR playback begins, ``False`` when it ends.
        '''
        self.stack.source = self.dvr.player if playback else self.source
        self.cameraWidget.setDisabled(playback)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop the filter stack, then the camera source.'''
        self.stack.stop()
        super().closeEvent(event)

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
        if not checked:
            return
        if button is self._modeRaw:
            self.dvr.source = self.source
        elif button is self._modeFiltered:
            self.dvr.source = self.stack
        elif button is self._modeDisplay:
            self.dvr.source = self.screen


def main() -> None:  # pragma: no cover
    '''Launch the filter rack demo with an interactively chosen camera.'''
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    from qtpy import QtGui
    app = pg.mkQApp('Filter Rack Demo')
    camera = choose_camera().start()
    widget = FilterRackDemo(camera)
    QtWidgets.QShortcut(
        QtGui.QKeySequence('Ctrl+Q'), widget
    ).activated.connect(app.quit)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
