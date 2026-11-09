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

#: Where an entry of the list keeps the control state of its browser.
_CONTROL = QtCore.Qt.ItemDataRole.UserRole + 1


class QWebShareDialog(QtWidgets.QDialog):

    '''The window for pairing a tablet with a
    :class:`~QVideo.lib.QWebScreen.QWebScreen`.

    While the window is open the web screen accepts the code that it shows:
    point the camera of a tablet or phone at it, and the browser opens the
    video.  Closing the window stops pairing and changes the secret, so
    only someone who could see the screen while it was open can pair, and
    each code pairs one device, after which a new code appears.  Browsers
    that paired stay paired until they are disconnected here.

    A paired browser can ask to control the camera (see
    :class:`~QVideo.lib.QWebScreen.QWebScreen`).  The dialog asks the
    operator, with a message box that appears whether or not the dialog is
    showing, and lists who controls.  **Take back control** ends it.

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
        self._prompts: dict[str, QtWidgets.QMessageBox] = {}
        web.codeChanged.connect(self._showCode)
        web.controlRequested.connect(self._askControl)
        web.viewersChanged.connect(self._showViewers)
        self._showCode()
        self._showViewers()
        self._showControlNote()

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
        if self.web.secure:
            notice = QtWidgets.QLabel('Encrypted (https).')
        else:
            notice = QtWidgets.QLabel(
                'Not encrypted: use this on a network that you trust.')
            notice.setStyleSheet('color: #a15c00;')
        notice.setWordWrap(True)
        self.controlNote = QtWidgets.QLabel()
        self.controlNote.setWordWrap(True)
        self.viewers = QtWidgets.QListWidget()
        self.viewers.setMaximumHeight(90)
        self.viewers.itemSelectionChanged.connect(self._enableDisconnect)
        self.disconnectButton = QtWidgets.QPushButton('Disconnect')
        self.disconnectButton.clicked.connect(self._disconnect)
        self.disconnectAllButton = QtWidgets.QPushButton('Disconnect all')
        self.disconnectAllButton.clicked.connect(self._disconnectAll)
        self.newCodeButton = QtWidgets.QPushButton('New code')
        self.newCodeButton.clicked.connect(self.web.rotate)
        self.takeBackButton = QtWidgets.QPushButton('Take back control')
        self.takeBackButton.clicked.connect(self._takeBack)
        buttons = QtWidgets.QGridLayout()
        buttons.addWidget(self.disconnectButton, 0, 0)
        buttons.addWidget(self.disconnectAllButton, 0, 1)
        buttons.addWidget(self.takeBackButton, 1, 0)
        buttons.addWidget(self.newCodeButton, 1, 1)
        layout = QtWidgets.QVBoxLayout(self)
        # The window is as tall as its contents need: with wrapped text the
        # layout otherwise lets it shrink until widgets overlap.
        layout.setSizeConstraint(
            QtWidgets.QLayout.SizeConstraint.SetFixedSize)
        layout.addWidget(self.code)
        layout.addWidget(self.address)
        layout.addWidget(hint)
        layout.addWidget(notice)
        layout.addWidget(self.controlNote)
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
        pixmap = QtGui.QPixmap.fromImage(self._draw(modules))
        self.code.setPixmap(pixmap)
        self.code.setFixedSize(pixmap.size())       # the layout cannot clip

    @staticmethod
    def _draw(modules: list[list[bool]]) -> QtGui.QImage:
        '''Return the picture of a code: black modules on white.'''
        count = len(modules) + 2 * _QUIET
        scale = max(3, _SIZE // count)
        side = max(_SIZE, count * scale)    # always the same size, if it fits
        offset = (side - count * scale) // 2 + _QUIET * scale
        image = QtGui.QImage(side, side, QtGui.QImage.Format.Format_RGB32)
        image.fill(QtGui.QColor('white'))
        painter = QtGui.QPainter(image)
        black = QtGui.QColor('black')
        for y, row in enumerate(modules):
            for x, dark in enumerate(row):
                if dark:
                    painter.fillRect(offset + x * scale, offset + y * scale,
                                     scale, scale, black)
        painter.end()
        return image

    def _showControlNote(self) -> None:
        '''Say what a paired browser can do about the camera.'''
        if self.web.camera is None:
            self.controlNote.hide()
            return
        if self.web.controlAvailable:
            names = ', '.join(self.web.controlNames)
            text = f'A tablet can ask to control: {names}.'
        else:
            text = f'View only: {self.web.controlReason}.'
        self.controlNote.setText(text)
        self.controlNote.show()

    @QtCore.Slot()
    def _showViewers(self) -> None:
        selected = self._selected()
        self.viewers.clear()
        wanted = {'requested': '  wants control', 'granted': '  controls'}
        viewers = self.web.viewers
        for viewer in viewers:
            state = 'watching' if viewer['watching'] else 'away'
            item = QtWidgets.QListWidgetItem(
                f"{viewer['name']}  {viewer['address']}  ({state})"
                + wanted.get(viewer['control'], ''))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, viewer['id'])
            item.setData(_CONTROL, viewer['control'])
            self.viewers.addItem(item)
            if viewer['id'] == selected:
                item.setSelected(True)
        self.disconnectAllButton.setEnabled(self.viewers.count() > 0)
        self._enableDisconnect()
        asking = {v['id'] for v in viewers if v['control'] == 'requested'}
        for ident in list(self._prompts):
            if ident not in asking:             # it gave up, or left
                self._withdraw(ident)

    def _selected(self) -> str | None:
        items = self.viewers.selectedItems()
        if not items:
            return None
        return items[0].data(QtCore.Qt.ItemDataRole.UserRole)

    @QtCore.Slot()
    def _enableDisconnect(self) -> None:
        self.disconnectButton.setEnabled(self._selected() is not None)
        items = self.viewers.selectedItems()
        self.takeBackButton.setEnabled(
            bool(items) and items[0].data(_CONTROL) == 'granted')

    @QtCore.Slot()
    def _takeBack(self) -> None:
        ident = self._selected()
        if ident is not None:
            self.web.revokeControl(ident)

    # ------------------------------------------------------------------
    # The operator answers a request
    # ------------------------------------------------------------------

    @QtCore.Slot(str)
    def _askControl(self, ident: str) -> None:
        '''Ask the operator whether the browser *ident* may control the
        camera.  Not modal: the instrument stays usable.'''
        if ident in self._prompts:
            return
        viewer = next((v for v in self.web.viewers if v['id'] == ident), None)
        if viewer is None:
            return
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        box.setWindowTitle('Allow control?')
        box.setText(f"{viewer['name']} ({viewer['address']}) wants to "
                    'control the camera.')
        box.setInformativeText(
            'It will be able to change: '
            + ', '.join(self.web.controlNames) + '.')
        role = QtWidgets.QMessageBox.ButtonRole
        allow = box.addButton('Allow', role.YesRole)
        deny = box.addButton('Deny', role.NoRole)
        box.setDefaultButton(deny)
        box.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        box.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        box.finished.connect(
            lambda _result, i=ident, b=box, a=allow: self._answered(i, b, a))
        self._prompts[ident] = box
        box.show()
        box.raise_()

    def _answered(self, ident: str, box: QtWidgets.QMessageBox,
                  allow: QtWidgets.QAbstractButton) -> None:
        if self._prompts.get(ident) is not box:
            return                      # withdrawn: nobody to answer
        del self._prompts[ident]
        if box.clickedButton() is allow:
            self.web.grantControl(ident)
        else:
            self.web.denyControl(ident)

    def _withdraw(self, ident: str) -> None:
        '''Close the prompt for a browser that no longer asks.'''
        box = self._prompts.pop(ident, None)
        if box is not None:
            box.close()

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
