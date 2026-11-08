#!/usr/bin/env python3
'''Demo: the video served to web browsers, such as a tablet.

Run directly::

    python -m QVideo.demos.webdemo

The window shows the address to open on the other device.  This needs
``aiohttp``: ``pip install "QVideo[stream]"``.
'''

import logging

from qtpy import QtCore, QtWidgets
from QVideo.demos.demo import Demo
from QVideo.lib import launch
from QVideo.lib.QWebScreen import QWebScreen


logger = logging.getLogger(__name__)

__all__ = ['WebDemo']


class WebDemo(Demo):

    '''The video on the screen, and in any browser that opens the address.

    Data flow::

        camera -> screen
              \\-> web screen -> browsers

    The recipe is one object that watches the same source as the screen:
    :class:`~QVideo.lib.QWebScreen.QWebScreen`.  It serves a page that shows
    the video, and the panel tells where to find it and how many browsers
    are watching.  Port 8080 is tried first; if it is taken, any free port
    is used.  See :class:`~QVideo.demos.demo.Demo` for the parameters.
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
        self.address = QtWidgets.QLabel(self.web.url)
        self.address.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.viewers = QtWidgets.QLabel()
        box = QtWidgets.QGroupBox('Web screen')
        layout = QtWidgets.QVBoxLayout(box)
        layout.addWidget(self.address)
        layout.addWidget(self.viewers)
        self._controls.addWidget(box)
        self.web.clientsChanged.connect(self._showViewers)
        self._showViewers(0)

    @QtCore.Slot(int)
    def _showViewers(self, count: int) -> None:
        self.viewers.setText(f'{count} watching')


if __name__ == '__main__':  # pragma: no cover
    launch(WebDemo, 'Web Demo')
