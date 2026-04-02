#!/usr/bin/env python3

'''Composite camcorder widget combining a video screen, camera controls, and DVR.

Run directly to launch a full camcorder application with camera selection::

    python -m QVideo.QCamcorder [-b|-c|-f|-i|-m|-p|-r|-v] [cameraID]

Camera flags (mutually exclusive):

.. code-block:: text

    -b [cameraID]   Basler camera (requires pylon SDK)
    -c [cameraID]   OpenCV camera
    -f [cameraID]   FLIR camera (requires Spinnaker SDK)
    -i [cameraID]   IDS Imaging camera (requires IDS peak SDK)
    -m [cameraID]   MATRIX VISION mvGenTLProducer (universal GenICam, not FLIR)
    -p [cameraID]   Raspberry Pi camera module (requires picamera2)
    -r [cameraID]   OpenCV camera with resolution drop-down selector
    -v [cameraID]   Allied Vision VimbaX camera
    -h              Show help and exit

If no flag is given, a noise camera is used as a fallback.
'''

from qtpy import QtCore, QtWidgets, QtGui, uic
from QVideo.lib import QCameraTree, QVideoSource
from pathlib import Path


__all__ = ['QCamcorder']


class QCamcorder(QtWidgets.QWidget):
    '''A widget combining a video screen, camera controls, and DVR.

    Lays out a :class:`~QVideo.lib.QVideoScreen.QVideoScreen` alongside
    a :class:`~QVideo.dvr.QDVRWidget.QDVRWidget` and an arbitrary
    :class:`~QVideo.lib.QCameraTree.QCameraTree` control panel.  Live
    frames from the camera source are routed to the screen; when the DVR
    starts playback the screen is switched to the playback stream and the
    camera controls are disabled until playback ends.

    Parameters
    ----------
    cameraWidget : QCameraTree
        Camera control tree to embed in the controls panel.
    *args :
        Additional positional arguments forwarded to
        :class:`~pyqtgraph.Qt.QtWidgets.QWidget`.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~pyqtgraph.Qt.QtWidgets.QWidget`.
    '''

    UIFILE = Path(__file__).parent / 'QCamcorder.ui'

    def __init__(self,
                 cameraWidget: QCameraTree,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraWidget = cameraWidget
        self._setupUi()
        self._connectSignals()
        self.screen.source = self.source
        self.dvr.source = self.source

    def _setupUi(self) -> None:
        uic.loadUi(str(self.UIFILE), self)
        self.controls.layout().addWidget(self.cameraWidget)
        self.layout().setStretch(0, 1)  # screen fill horizontal space
        self.layout().setStretch(1, 0)  # controls retain natural width

    def _connectSignals(self) -> None:
        self.dvr.playing.connect(self.dvrPlayback)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop the camera source when the widget is closed.'''
        self.cameraWidget.stop()
        super().closeEvent(event)

    @QtCore.Slot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        '''Switch the screen source between live camera and DVR playback.

        Connected to :attr:`~QVideo.dvr.QDVRWidget.QDVRWidget.playing`.
        When playback starts the camera source is disconnected from the
        screen and the DVR's :attr:`~QVideo.dvr.QDVRWidget.QDVRWidget.newFrame`
        signal is connected instead; the camera controls are disabled.
        When playback ends the connections are reversed and the controls
        are re-enabled.

        Parameters
        ----------
        playback : bool
            ``True`` when DVR playback begins, ``False`` when it ends.
        '''
        try:
            if playback:
                self.source.newFrame.disconnect(self.screen.setImage)
                self.dvr.newFrame.connect(self.screen.setImage)
            else:
                self.dvr.newFrame.disconnect(self.screen.setImage)
                self.source.newFrame.connect(self.screen.setImage)
        except (RuntimeError, TypeError):
            pass
        self.cameraWidget.setDisabled(playback)

    @property
    def source(self) -> QVideoSource:
        '''The :class:`~QVideo.lib.QVideoSource.QVideoSource` from the camera widget.'''
        return self.cameraWidget.source


def main() -> None:  # pragma: no cover
    '''Launch the camcorder with an interactively chosen camera.'''
    import pyqtgraph as pg
    from QVideo.lib import choose_camera

    pg.mkQApp('QCamcorder')
    camera = choose_camera()
    widget = QCamcorder(camera.start())
    widget.show()
    pg.exec()


if __name__ == '__main__':
    main()
