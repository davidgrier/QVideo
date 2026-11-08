#!/usr/bin/env python3

'''Composite camcorder widget combining a video screen, camera controls,
and DVR.

Run directly to launch a full camcorder application with camera selection::

    python -m QVideo.QCamcorder [-b|-c|-f|-g|-i|-m|-p|-v] [cameraID]

Camera flags (mutually exclusive):

.. code-block:: text

    -b [cameraID]   Basler camera (requires pylon SDK)
    -c [cameraID]   OpenCV camera
    -f [cameraID]   FLIR camera (requires Spinnaker SDK)
    -g [cameraID]   GenICam camera via viva-genicam (preferred; no vendor SDK)
    -i [cameraID]   IDS Imaging camera (requires IDS peak SDK)
    -m [cameraID]   MATRIX VISION mvGenTLProducer (universal GenICam, not FLIR)
    -p [cameraID]   Raspberry Pi camera module (requires picamera2)
    -v [cameraID]   Allied Vision VimbaX camera
    -h              Show help and exit

If no flag is given, a noise camera is used as a fallback.
'''

import numpy as np
from qtpy import QtCore, QtWidgets, QtGui
from QVideo.lib import (QCameraTree, QVideoSource, QVideoScreen, QSnapshot,
                        launch)
from QVideo.widgets import QScrollPanel
from QVideo.dvr import QDVRWidget


__all__ = ['QCamcorder']

#: Compact layout of the screen and the controls [pixels].
_MARGINS = (4, 4, 4, 4)
_SPACING = 3

#: The ways to map the counts of a camera of more than 8 bits to the screen.
_LEVELS = ('Levels: camera range', 'Levels: auto contrast',
           'Levels: full 16 bits')

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
    ``newFrame`` signal and to the screen itself.  Four hotkeys save a still
    frame, and the status bar says where it went:

    - ``Ctrl+Shift+S`` — save the frame (the data) to a timestamped PNG in
      the home directory
    - ``Ctrl+Shift+Alt+S`` — the same, in a file dialog pre-filled with the
      name
    - ``Ctrl+Shift+P`` — save what the screen shows (filters, color map and
      overlays) to a timestamped PNG
    - ``Ctrl+Shift+Alt+P`` — the same, in a file dialog

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
        self._snapshot = QSnapshot(self, screen=self.screen)
        self._connectSignals()

    def _setupUi(self) -> None:
        self.screen = QVideoScreen(self)
        self.dvr = QDVRWidget(self, key='dvr')
        self.screen.source = self.source
        self.dvr.source = self.source

        self.controls = QtWidgets.QWidget(self)
        self._controls = QtWidgets.QVBoxLayout(self.controls)
        self._controls.setContentsMargins(*_MARGINS)
        self._controls.setSpacing(_SPACING)
        self._controls.addWidget(self.dvr)
        self.levelsBox = QtWidgets.QComboBox(self)
        self.levelsBox.addItems(_LEVELS)
        self.levelsBox.setToolTip(
            'How the display maps the counts of the camera to black and '
            'white.  The recorded data are not changed.')
        self.levelsBox.hide()           # until a camera has more than 8 bits
        self._controls.addWidget(self.levelsBox)
        self._controls.addWidget(self.cameraWidget)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(*_MARGINS)
        layout.setSpacing(_SPACING)
        layout.addWidget(self.screen)
        layout.addWidget(QScrollPanel(self.controls))
        layout.setStretch(0, 1)
        layout.setStretch(1, 0)

    def _connectSignals(self) -> None:
        self.dvr.playing.connect(self.dvrPlayback)
        self.dvr.recording.connect(self._clearMessage)
        self.dvr.backlog.connect(self._showBacklog)
        # Queued, so that the reason follows the end of the recording,
        # which clears the message.
        self.dvr.stopped.connect(self.message, QtCore.Qt.QueuedConnection)
        self.dvr.stopped.connect(self._showStopped,
                                 QtCore.Qt.QueuedConnection)
        self.source.lost.connect(self._showLost)
        self.screen.newFrame.connect(self._snapshot.newFrame)
        self._snapshot.saver.message.connect(self.message)
        self.screen.newFrame.connect(self._offerLevels)
        self.levelsBox.currentIndexChanged.connect(self._setLevels)

    @QtCore.Slot(np.ndarray, object)
    def _offerLevels(self, _frame: np.ndarray, info: object) -> None:
        '''Show the choice of levels once a frame brings its own.'''
        if (self.levelsBox.isHidden()
                and getattr(info, 'levels', None) is not None):
            self.levelsBox.show()

    @QtCore.Slot(int)
    def _setLevels(self, index: int) -> None:
        '''Display the counts between the camera's range, a percentile
        range of the frame, or the whole range of 16 bits.'''
        self.screen.levels = (0, 65535) if index == 2 else None
        self.screen.autoLevels = (1, 99) if index == 1 else None

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

    @QtCore.Slot(str)
    def _showStopped(self, reason: str) -> None:
        '''Tell the user why a recording stopped by itself.

        The status bar is easy to miss while watching the video, and a
        recording that ends without notice can lose data.
        '''
        self._warn('Recording stopped', 'The recording stopped.',
                   reason[:1].upper() + reason[1:] + '.')

    @QtCore.Slot(str)
    def _showLost(self, reason: str) -> None:
        '''Tell the user that the camera has gone.

        The screen keeps the last frame and everything else carries on, so
        nothing else says why the picture is still.  A recording that is
        running waits for frames that will not come: stop it.
        '''
        self.message.emit('Camera lost.  Restart the program to use it again.')
        self._warn('Camera lost', 'Lost contact with the camera.',
                   'No more images will arrive, and the last one stays on '
                   'the screen.  Stop any recording that is running, then '
                   'restart the program to use the camera again.',
                   details=reason[:1].upper() + reason[1:] + '.')

    def _warn(self, title: str, headline: str, explanation: str = '',
              details: str = '') -> None:
        '''Show a warning dialog that does not block.

        The headline is short and says what happened; the explanation says
        what it means and what to do; the details, behind a button, are for
        the technical text that a backend gives.  The dialog is not modal: a
        modal loop would hold up the frames that the screen is showing.
        '''
        box = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Icon.Warning, title, headline,
            parent=self)
        box.setInformativeText(explanation)
        if details:
            box.setDetailedText(details)
        box.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self._stopBox = box
        box.open()

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
