'''A window that shows the QR code that lets a tablet watch the video.'''
from __future__ import annotations

import logging

from qtpy import QtCore, QtGui, QtWidgets

from QVideo.lib import _qrcode
from QVideo.lib.QWebScreen import QWebScreen


logger = logging.getLogger(__name__)

__all__ = ['QWebShareDialog']

#: Modules of quiet zone around the code (the standard asks for four).
_QUIET = 4

#: The width of the code on the screen [pixels], about.
_SIZE = 280


class QWebShareDialog(QtWidgets.QDialog):

    '''The window for pairing a tablet with a
    :class:`~QVideo.lib.QWebScreen.QWebScreen`.

    While the window is open the web screen accepts the code that it shows:
    point the camera of a tablet or phone at it, and the browser opens the
    video.  Closing the window stops pairing and changes the secret, so
    only someone who could see the screen while it was open can pair, and
    each code pairs one device, after which a new code appears.  Browsers
    that paired stay paired until they are disconnected here.

    The window is not modal: the instrument stays usable while it is open.
    A program shows it from a button, a menu item or a shortcut with
    :meth:`toggle`.

    Parameters
    ----------
    web : QWebScreen
        The web screen to pair browsers with.  It must be started.
    parent : QWidget, optional
        The window that this one belongs to.
    '''

    def __init__(self, web: QWebScreen,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.web = web
        self.setWindowTitle('Watch on a tablet')
        self._setupUi()
        web.codeChanged.connect(self._showCode)
        web.viewersChanged.connect(self._showViewers)
        self._showCode()
        self._showViewers()

    def _setupUi(self) -> None:
        self.code = QtWidgets.QLabel()
        self.code.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.address = QtWidgets.QLabel()
        self.address.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.address.setWordWrap(True)
        self.address.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        hint = QtWidgets.QLabel(
            'Point the camera of the tablet at the code.  Each code pairs '
            'one device, and a new one appears.  Only people who can see '
            'this window can pair; closing it changes the code.')
        hint.setWordWrap(True)
        notice = QtWidgets.QLabel(
            'Not encrypted: use this on a network that you trust.')
        notice.setWordWrap(True)
        notice.setStyleSheet('color: #a15c00;')
        self.viewers = QtWidgets.QListWidget()
        self.viewers.setMaximumHeight(90)
        self.viewers.itemSelectionChanged.connect(self._enableDisconnect)
        self.disconnectButton = QtWidgets.QPushButton('Disconnect')
        self.disconnectButton.clicked.connect(self._disconnect)
        self.disconnectAllButton = QtWidgets.QPushButton('Disconnect all')
        self.disconnectAllButton.clicked.connect(self._disconnectAll)
        self.newCodeButton = QtWidgets.QPushButton('New code')
        self.newCodeButton.clicked.connect(self.web.rotate)
        buttons = QtWidgets.QHBoxLayout()
        for button in (self.disconnectButton, self.disconnectAllButton,
                       self.newCodeButton):
            buttons.addWidget(button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.code)
        layout.addWidget(self.address)
        layout.addWidget(hint)
        layout.addWidget(notice)
        layout.addWidget(QtWidgets.QLabel('Paired:'))
        layout.addWidget(self.viewers)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    # Showing and hiding
    # ------------------------------------------------------------------

    @QtCore.Slot()
    def toggle(self) -> None:
        '''Show the window, or close it if it is showing.'''
        if self.isVisible():
            self.close()
        else:
            self.show()
            self.raise_()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self.web.openPairing()
        self._showCode()
        super().showEvent(event)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        if not event.spontaneous():     # minimizing does not close it
            self.web.closePairing()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # What it shows
    # ------------------------------------------------------------------

    @QtCore.Slot()
    def _showCode(self) -> None:
        url = self.web.pairingUrl
        self.address.setText(url)
        try:
            modules = _qrcode.matrix(url)
        except ImportError:
            self.code.setText('Install segno (pip install "QVideo[stream]") '
                              'to see a QR code.  Open this address '
                              'instead:')
            return
        self.code.setPixmap(QtGui.QPixmap.fromImage(self._draw(modules)))

    @staticmethod
    def _draw(modules: list[list[bool]]) -> QtGui.QImage:
        '''Return the picture of a code: black modules on white.'''
        count = len(modules) + 2 * _QUIET
        scale = max(3, _SIZE // count)
        image = QtGui.QImage(count * scale, count * scale,
                             QtGui.QImage.Format.Format_RGB32)
        image.fill(QtGui.QColor('white'))
        painter = QtGui.QPainter(image)
        black = QtGui.QColor('black')
        for y, row in enumerate(modules):
            for x, dark in enumerate(row):
                if dark:
                    painter.fillRect((x + _QUIET) * scale,
                                     (y + _QUIET) * scale,
                                     scale, scale, black)
        painter.end()
        return image

    @QtCore.Slot()
    def _showViewers(self) -> None:
        selected = self._selected()
        self.viewers.clear()
        for viewer in self.web.viewers:
            state = 'watching' if viewer['watching'] else 'away'
            item = QtWidgets.QListWidgetItem(
                f"{viewer['name']}  {viewer['address']}  ({state})")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, viewer['id'])
            self.viewers.addItem(item)
            if viewer['id'] == selected:
                item.setSelected(True)
        self.disconnectAllButton.setEnabled(self.viewers.count() > 0)
        self._enableDisconnect()

    def _selected(self) -> str | None:
        items = self.viewers.selectedItems()
        if not items:
            return None
        return items[0].data(QtCore.Qt.ItemDataRole.UserRole)

    @QtCore.Slot()
    def _enableDisconnect(self) -> None:
        self.disconnectButton.setEnabled(self._selected() is not None)

    @QtCore.Slot()
    def _disconnectAll(self) -> None:
        # not connected to web.revoke directly: clicked sends a bool
        self.web.revoke()

    @QtCore.Slot()
    def _disconnect(self) -> None:
        ident = self._selected()
        if ident is not None:
            self.web.revoke(ident)


if __name__ == '__main__':  # pragma: no cover
    import sys
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
        sys.argv)
    web = QWebScreen(port=0).start()
    dialog = QWebShareDialog(web)
    dialog.show()
    app.exec()
    web.stop()
