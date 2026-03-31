#!/usr/bin/env python3
'''Camcorder demo with trackpy overlay and composite recording.

Run directly::

    python -m QVideo.demos.compositedemo

When the "Composite" checkbox is checked, the DVR records the rendered
scene — video frame plus trackpy particle markers — instead of raw
camera frames.
'''

from qtpy import QtCore, QtWidgets
from QVideo.QCamcorder import QCamcorder
from QVideo.lib import QCameraTree
from QVideo.overlays import QTrackpyWidget


__all__ = ['CompositeDemo']


class CompositeDemo(QCamcorder):
    '''Camcorder with a trackpy overlay and composite-recording toggle.

    Extends :class:`~QVideo.QCamcorder.QCamcorder` by adding a
    :class:`~QVideo.overlays.trackpy.QTrackpyWidget` control panel and a
    "Composite" checkbox to the controls column.

    When the checkbox is unchecked (default), the DVR records raw camera
    frames as usual.  When checked, :attr:`~QVideo.lib.QVideoScreen.QVideoScreen.composite`
    is enabled on the screen and the DVR is switched to record from the
    screen, capturing each displayed frame with the trackpy markers
    composited in.

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
        self.trackpy = QTrackpyWidget(self)
        self.trackpy.source = self.source
        self.screen.addOverlay(self.trackpy.overlay)
        self._compositeCheck = QtWidgets.QCheckBox('Composite')
        self._compositeCheck.toggled.connect(self._onCompositeToggled)
        self.controls.layout().addWidget(self.trackpy)
        self.controls.layout().addWidget(self._compositeCheck)

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


def main() -> None:  # pragma: no cover
    '''Launch the composite demo with an interactively chosen camera.'''
    import sys
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    pg.mkQApp()
    camera = choose_camera().start()
    try:
        widget = CompositeDemo(camera)
    except ImportError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    widget.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
