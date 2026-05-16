#!/usr/bin/env python3
'''Camcorder with an interactive filter rack and three recording modes.

Run directly::

    python -m QVideo.demos.filterrackdemo

The filter rack starts with :class:`~QVideo.filters.QSmoothingFilter.QSmoothingFilter`
and :class:`~QVideo.filters.QThresholdFilter.QThresholdFilter` pre-loaded.
Additional filters can be added interactively via the "Add filter…" button,
and any filter can be removed or reordered by dragging.

Three recording modes are offered:

**Raw**
    The unfiltered camera stream at the full camera frame rate.

**Filtered**
    The rack-processed stream at the full camera frame rate.  Every
    frame is filtered, regardless of the display throttle.

**Display**
    The rack-processed stream at the throttled display rate.  Only
    frames that are actually rendered to screen are recorded.
'''

import numpy as np
from qtpy import QtCore, QtWidgets
from QVideo.QCamcorder import QCamcorder
from QVideo.lib import QCameraTree, QFilterRack
from QVideo.filters import QSmoothingFilter, QThresholdFilter
from QVideo.lib.videotypes import Image


__all__ = ['FilterRackDemo']


class _FilteredSource(QtCore.QObject):
    '''Applies a :class:`~QVideo.lib.QFilterRack.QFilterRack` to every frame
    from a source at the camera's full frame rate.

    Connects to ``source.newFrame``, passes each frame through the rack,
    and re-emits the result.  This gives the DVR a valid source for
    filtered full-speed recording, independent of the display throttle.

    Parameters
    ----------
    source : QVideoSource
        The raw camera source to intercept.
    rack : QFilterRack
        The filter rack to apply to each frame.
    parent : QtWidgets.QWidget or None
        Parent object.
    '''

    newFrame = QtCore.Signal(np.ndarray)

    def __init__(self,
                 source,
                 rack: QFilterRack,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._source = source
        self._rack = rack
        self._active = True
        source.newFrame.connect(self._process)

    @property
    def fps(self) -> float | None:
        '''Frame rate of the underlying source [fps].'''
        return self._source.fps

    def setActive(self, active: bool) -> None:
        '''Connect or disconnect from the source.

        Parameters
        ----------
        active : bool
            ``True`` to resume processing; ``False`` to pause.
        '''
        if active == self._active:
            return
        self._active = active
        if active:
            self._source.newFrame.connect(self._process)
        else:
            self._source.newFrame.disconnect(self._process)

    @QtCore.Slot(np.ndarray)
    def _process(self, frame: Image) -> None:
        self.newFrame.emit(self._rack(frame))


class FilterRackDemo(QCamcorder):
    '''Camcorder with an interactive filter rack and three recording modes.

    Extends :class:`~QVideo.QCamcorder.QCamcorder` by adding a
    :class:`~QVideo.lib.QFilterRack.QFilterRack` pre-loaded with
    :class:`~QVideo.filters.QSmoothingFilter.QSmoothingFilter` and
    :class:`~QVideo.filters.QThresholdFilter.QThresholdFilter`, and
    a group of radio buttons to select the DVR recording source:

    - **Raw**: unfiltered frames at the camera's full frame rate.
    - **Filtered**: rack-processed frames at the camera's full frame rate.
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
        self.screen.filter = self.rack
        self._filteredSource = _FilteredSource(self.source, self.rack, self)
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
        '''Pause the filtered source during DVR playback.

        Extends :meth:`~QVideo.QCamcorder.QCamcorder.dvrPlayback` by
        suspending :class:`_FilteredSource` while the DVR is playing.
        This prevents live camera frames from racing through the shared
        filter rack alongside DVR frames, which would corrupt
        :class:`~QVideo.lib.AsyncVideoFilter.AsyncVideoFilter` results.

        Parameters
        ----------
        playback : bool
            ``True`` when DVR playback begins, ``False`` when it ends.
        '''
        super().dvrPlayback(playback)
        self._filteredSource.setActive(not playback)

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
            self.dvr.source = self._filteredSource
        elif button is self._modeDisplay:
            self.dvr.source = self.screen


def main() -> None:  # pragma: no cover
    '''Launch the filter rack demo with an interactively chosen camera.'''
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    pg.mkQApp('Filter Rack Demo')
    camera = choose_camera().start()
    widget = FilterRackDemo(camera)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
