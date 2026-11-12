#!/usr/bin/env python3
'''Demo: the video served to web browsers, such as a tablet.

Run directly::

    python -m QVideo.demos.webdemo

The window opens the sharing window, with the QR code that pairs a tablet:
point the tablet's camera at it.  Ctrl+Shift+W (or the Share button) shows
or closes it.  This needs ``aiohttp`` and ``segno``:
``pip install "QVideo[stream]"``.
'''

import logging

from qtpy import QtCore, QtGui, QtWidgets
from QVideo.QCamcorder import QCamcorder
from QVideo.lib import launch
from QVideo.lib.QWebScreen import QWebScreen
from QVideo.widgets.QWebShareDialog import QWebShareDialog


logger = logging.getLogger(__name__)

__all__ = ['WebDemo']


class WebDemo(QCamcorder):

    '''A camcorder whose video can also be watched on a tablet or phone.

    Data flow::

        camera -> screen
              \\-> dvr
              \\-> web screen -> browsers

    The recipe is one object that watches the same source as the screen:
    :class:`~QVideo.lib.QWebScreen.QWebScreen`.  It serves a page that shows
    the video to browsers that have paired, and the panel has a Share button
    that opens the QR code
    (:class:`~QVideo.widgets.QWebShareDialog.QWebShareDialog`) and says how
    many are watching.  The window opens when the demo starts.  Port 8080 is
    tried first; if it is taken, any free port is used.  The camcorder
    itself is unchanged, and has no web code: sharing is this recipe.
    '''

    #: A subclass that has a certificate sets these (PEM files): the page
    #: is then served over https,
    #: and the name that the certificate covers, which the QR code uses.
    certfile: str | None = None
    keyfile: str | None = None
    hostname: str | None = None

    #: A demo is tier 1 (plain http, a network that you trust): it lets a
    #: tablet control the camera without a certificate, to try it.  An
    #: application should leave this ``False`` or give a certificate: see
    #: :class:`~QVideo.lib.QWebScreen.QWebScreen`.
    controlOverHttp: bool = True

    def _setupUi(self) -> None:
        super()._setupUi()
        self.web = QWebScreen(self.screen.source, certfile=self.certfile,
                              keyfile=self.keyfile,
                              hostname=self.hostname,
                              camera=self.cameraWidget.camera,
                              controlOverHttp=self.controlOverHttp)
        self.web.start(fallback=True)
        self.share = QWebShareDialog(self.web, self)
        self.shareButton = QtWidgets.QPushButton('Share...')
        self.shareButton.setToolTip('Show the QR code (Ctrl+Shift+W)')
        self.shareButton.clicked.connect(self.share.toggle)
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence('Ctrl+Shift+W'), self)
        shortcut.setContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.share.toggle)
        self.viewers = QtWidgets.QLabel()
        box = QtWidgets.QGroupBox('Web screen')
        layout = QtWidgets.QVBoxLayout(box)
        layout.addWidget(self.shareButton)
        layout.addWidget(self.viewers)
        self._controls.addWidget(box)
        self.web.clientsChanged.connect(self._showViewers)
        self._showViewers(0)
        QtCore.QTimer.singleShot(0, self.share.show)

    @QtCore.Slot(int)
    def _showViewers(self, count: int) -> None:
        self.viewers.setText(f'{count} watching')


if __name__ == '__main__':  # pragma: no cover
    launch(WebDemo, 'Web Demo')
