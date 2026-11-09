'''Unit tests for QWebShareDialog.'''
import unittest
from unittest.mock import patch

from qtpy import QtWidgets

from QVideo.lib import _qrcode
from QVideo.lib.QWebScreen import QWebScreen, _Viewer
from QVideo.widgets.QWebShareDialog import QWebShareDialog

try:
    import segno
except ImportError:                     # pragma: no cover
    segno = None


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestDialog(unittest.TestCase):

    '''The dialog needs no running server: the web screen is only a model.'''

    def setUp(self):
        self.web = QWebScreen(host='127.0.0.1', port=8099)
        self.dialog = QWebShareDialog(self.web)
        self.addCleanup(self.dialog.deleteLater)

    def test_showing_opens_pairing_and_closing_ends_it(self):
        self.assertFalse(self.web.pairing)
        self.dialog.show()
        self.assertTrue(self.web.pairing)
        self.dialog.close()
        self.assertFalse(self.web.pairing)

    def test_toggle(self):
        self.dialog.toggle()
        self.assertTrue(self.dialog.isVisible())
        self.dialog.toggle()
        self.assertFalse(self.dialog.isVisible())
        self.assertFalse(self.web.pairing)

    def test_closing_changes_the_code(self):
        self.dialog.show()
        shown = self.dialog.address.text()
        self.assertEqual(shown, self.web.pairingUrl)
        self.dialog.close()
        self.assertNotEqual(self.dialog.address.text(), shown)

    def test_a_new_code_is_shown(self):
        self.dialog.show()
        shown = self.dialog.address.text()
        self.dialog.newCodeButton.click()
        self.assertNotEqual(self.dialog.address.text(), shown)
        self.assertEqual(self.dialog.address.text(), self.web.pairingUrl)

    @unittest.skipIf(segno is None, 'segno not installed')
    def test_the_code_is_a_picture(self):
        self.dialog.show()
        pixmap = self.dialog.code.pixmap()
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), pixmap.height())

    def test_without_segno_the_address_is_still_shown(self):
        with patch.dict('sys.modules', {'segno': None}):
            self.dialog.show()
        self.assertIn('segno', self.dialog.code.text())
        self.assertEqual(self.dialog.address.text(), self.web.pairingUrl)

    def test_the_viewers_are_listed_and_can_be_disconnected(self):
        viewer = _Viewer('abc', '10.0.0.7', 'Mozilla (iPad)')
        self.web._sessions['abc'] = viewer
        self.web.viewersChanged.emit()
        self.assertEqual(self.dialog.viewers.count(), 1)
        self.assertIn('iPad', self.dialog.viewers.item(1 - 1).text())
        self.assertFalse(self.dialog.disconnectButton.isEnabled())
        self.assertTrue(self.dialog.disconnectAllButton.isEnabled())
        self.dialog.viewers.setCurrentRow(0)
        self.assertTrue(self.dialog.disconnectButton.isEnabled())
        self.dialog.disconnectButton.click()
        self.assertEqual(self.web.viewers, [])
        self.assertEqual(self.dialog.viewers.count(), 0)
        self.assertFalse(self.dialog.disconnectAllButton.isEnabled())


@unittest.skipIf(segno is None, 'segno not installed')
class TestQrcode(unittest.TestCase):

    def test_the_matrix_is_square(self):
        modules = _qrcode.matrix('http://10.0.0.1:8080/join/abc')
        self.assertTrue(all(len(row) == len(modules) for row in modules))
        self.assertTrue(any(any(row) for row in modules))

    def test_the_terminal_text_has_lines(self):
        self.assertGreater(len(_qrcode.terminal('x').splitlines()), 5)

    def test_without_segno_it_says_what_to_install(self):
        with patch.dict('sys.modules', {'segno': None}):
            with self.assertRaisesRegex(ImportError, r'QVideo\[stream\]'):
                _qrcode.matrix('x')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
