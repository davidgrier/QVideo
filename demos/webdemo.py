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
from QVideo.demos.demo import Demo
from QVideo.lib import launch
from QVideo.lib.QWebScreen import QWebScreen
from QVideo.widgets.QWebShareDialog import QWebShareDialog


logger = logging.getLogger(__name__)

__all__ = ['WebDemo']


class WebDemo(Demo):

    '''The video on the screen, and in any browser that opens the address.

    Data flow::

        camera -> screen
              \\-> web screen -> browsers

    The recipe is one object that watches the same source as the screen:
    :class:`~QVideo.lib.QWebScreen.QWebScreen`.  It serves a page that shows
    the video to browsers that have paired, and the panel has a Share button
    that opens the QR code
    (:class:`~QVideo.widgets.QWebShareDialog.QWebShareDialog`) and says how
    many are watching.  The window opens when the demo starts.  Port 8080 is
    tried first; if it is taken, any free port is used.  See
    :class:`~QVideo.demos.demo.Demo` for the parameters.
    '''

    def _setupUi(self) -> None:
        super()._setupUi()
        self.web = QWebScreen(self.screen.source)
        try:
            self.web.start()
        except OSError:
            logger.info('port 8080 is taken: using another')
            self.web.port = 0
            self.web.start()
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
