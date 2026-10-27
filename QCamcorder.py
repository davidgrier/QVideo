#!/usr/bin/env python3

'''Composite camcorder widget combining a video screen, camera controls,
and DVR.

Run directly to launch a full camcorder application with camera selection::

    python -m QVideo.QCamcorder [-b|-c|-f|-i|-m|-p|-v] [cameraID]

Camera flags (mutually exclusive):

.. code-block:: text

    -b [cameraID]   Basler camera (requires pylon SDK)
    -c [cameraID]   OpenCV camera
    -f [cameraID]   FLIR camera (requires Spinnaker SDK)
    -i [cameraID]   IDS Imaging camera (requires IDS peak SDK)
    -m [cameraID]   MATRIX VISION mvGenTLProducer (universal GenICam, not FLIR)
    -p [cameraID]   Raspberry Pi camera module (requires picamera2)
    -v [cameraID]   Allied Vision VimbaX camera
    -h              Show help and exit

If no flag is given, a noise camera is used as a fallback.
'''

from qtpy import QtCore, QtWidgets, QtGui
from QVideo.lib import (QCameraTree, QVideoSource, QVideoScreen, QSnapshot,
                        launch)
from QVideo.dvr import QDVRWidget


__all__ = ['QCamcorder']

#: Compact layout of the screen and the controls [pixels].
_MARGINS = (4, 4, 4, 4)
_SPACING = 3

#: Backlog, as a fraction of the allowance, from which it is shown.
_SHOW_BACKLOG = 0.25


class QCamcorder(QtWidgets.QWidget):
    '''A widget combining a video screen, camera controls, and DVR.

    Lays out a :class:`~QVideo.lib.QVideoScreen.QVideoScreen` alongside
    a :class:`~QVideo.dvr.QDVRWidget.QDVRWidget` and an arbitrary
    :class:`~QVideo.lib.QCameraTree.QCameraTree` control panel.  Live
    frames from the camera source are routed to the screen; when the DVR
    starts playback the screen is switched to the playback stream and the
    camera controls are disabled until playback ends.

    A subclass adds an idea by overriding :meth:`_setupUi`: it calls
    ``super()._setupUi()`` first, then builds its widgets, connects them
    and adds them to the panel of controls, ``self._controls``.  See
    :mod:`QVideo.demos` for examples.

    The widget emits :attr:`message` to warn when a recording starts to fall
    behind the camera and to say why when the DVR stops one.  The host
    decides where to show it, for instance in the status bar of its main
    window, as :func:`~QVideo.lib.launch` does.

    A :class:`~QVideo.lib.QSnapshot.QSnapshot` is wired to the screen's
    ``newFrame`` signal, enabling still-frame capture via two hotkeys:

    - ``Ctrl+Shift+S`` — save a timestamped PNG to the home directory
    - ``Ctrl+Shift+Alt+S`` — open a file dialog pre-filled with the same name

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

    Signals
    -------
    message(str)
        Text for the user, or an empty string to clear it.
    '''

    #: Emitted with text for the user, or ``''`` to clear it.
    message = QtCore.Signal(str)

    def __init__(self,
                 cameraWidget: QCameraTree,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraWidget = cameraWidget
        self._setupUi()
        self._snapshot = QSnapshot(self)
        self._connectSignals()

    def _setupUi(self) -> None:
        self.screen = QVideoScreen(self)
        self.dvr = QDVRWidget(self)
        self.screen.source = self.source
        self.dvr.source = self.source

        self.controls = QtWidgets.QWidget(self)
        self._controls = QtWidgets.QVBoxLayout(self.controls)
        self._controls.setContentsMargins(*_MARGINS)
        self._controls.setSpacing(_SPACING)
        self._controls.addWidget(self.dvr)
        self._controls.addWidget(self.cameraWidget)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(*_MARGINS)
        layout.setSpacing(_SPACING)
        layout.addWidget(self.screen)
        layout.addWidget(self.controls)
        layout.setStretch(0, 1)
        layout.setStretch(1, 0)

    def _connectSignals(self) -> None:
        self.dvr.playing.connect(self.dvrPlayback)
        self.dvr.recording.connect(self._clearMessage)
        self.dvr.backlog.connect(self._showBacklog)
        # Queued, so that the reason follows the end of the recording,
        # which clears the message.
        self.dvr.stopped.connect(self.message, QtCore.Qt.QueuedConnection)
        self.screen.newFrame.connect(self._snapshot.newFrame)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop the camera source when the widget is closed.

        Note: Qt only calls ``closeEvent`` on top-level windows.  When
        QCamcorder is embedded as a child widget, closing the parent
        window will not invoke this method; camera cleanup is then
        handled by ``QCameraTree``\'s ``aboutToQuit`` connection.
        '''
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
        played = self.dvr.playback.source
        self.screen.source = played if playback else self.source
        self.cameraWidget.setDisabled(playback)

    @QtCore.Slot(bool)
    def _clearMessage(self, recording: bool) -> None:
        '''Clear the message when a recording starts or ends.'''
        self.message.emit('')

    @QtCore.Slot(float)
    def _showBacklog(self, fraction: float) -> None:
        '''Warn while the writer falls behind the camera.'''
        self.message.emit(f'Writer backlog: {fraction:.0%} of the limit'
                          if fraction >= _SHOW_BACKLOG else '')

    @property
    def source(self) -> QVideoSource:
        '''The :class:`~QVideo.lib.QVideoSource.QVideoSource` from the
        camera widget.'''
        return self.cameraWidget.source


def main() -> None:  # pragma: no cover
    '''Launch the camcorder with an interactively chosen camera.'''
    launch(QCamcorder, 'QCamcorder')


if __name__ == '__main__':
    main()
