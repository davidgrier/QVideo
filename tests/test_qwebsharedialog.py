'''Unit tests for QWebShareDialog.'''
import unittest
from unittest.mock import patch

from qtpy import QtWidgets

from QVideo.cameras.Noise import QNoiseCamera

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

    def test_disconnect_all_removes_every_viewer(self):
        for name in 'ab':
            self.web._sessions[name] = _Viewer(name, '10.0.0.7', 'iPad')
        self.web.viewersChanged.emit()
        self.assertEqual(self.dialog.viewers.count(), 2)
        self.dialog.disconnectAllButton.click()
        self.assertEqual(self.web.viewers, [])
        self.assertEqual(self.dialog.viewers.count(), 0)


class TestControlPrompt(unittest.TestCase):

    '''The operator answers a browser that asks to control the camera.'''

    def setUp(self):
        self.camera = QNoiseCamera()
        self.addCleanup(self.camera.close)
        self.web = QWebScreen(host='127.0.0.1', port=8099,
                              camera=self.camera, controlOverHttp=True)
        self.dialog = QWebShareDialog(self.web)
        self.addCleanup(self.dialog.deleteLater)
        self.viewer = _Viewer('abc', '10.0.0.7', 'Mozilla (iPad)')
        self.web._sessions['abc'] = self.viewer

    def ask(self):
        self.viewer.control = 'requested'
        self.web.controlRequested.emit('abc')
        app.processEvents()
        return self.dialog._prompts.get('abc')

    @staticmethod
    def press(box, text):
        (button,) = [b for b in box.buttons() if b.text() == text]
        button.click()

    def test_a_request_raises_a_prompt_that_names_the_browser(self):
        box = self.ask()
        self.assertTrue(box.isVisible())
        self.assertIn('iPad', box.text())
        self.assertIn('10.0.0.7', box.text())
        self.assertIn('blacklevel', box.informativeText())
        box.close()

    def test_allow_grants_control(self):
        box = self.ask()
        self.press(box, 'Allow')
        self.assertEqual(self.web.controller, 'abc')
        self.assertNotIn('abc', self.dialog._prompts)

    def test_deny_refuses_control(self):
        box = self.ask()
        self.press(box, 'Deny')
        self.assertIsNone(self.web.controller)
        self.assertEqual(self.viewer.control, 'none')
        self.assertGreater(self.viewer.deniedAt, 0)

    def test_closing_the_prompt_is_a_refusal(self):
        box = self.ask()
        box.close()
        self.assertEqual(self.viewer.control, 'none')
        self.assertIsNone(self.web.controller)

    def test_a_request_that_is_withdrawn_closes_the_prompt(self):
        box = self.ask()
        self.viewer.control = 'none'            # the page gave up
        self.web.viewersChanged.emit()
        self.assertNotIn('abc', self.dialog._prompts)
        self.assertFalse(box.isVisible())

    def test_the_prompt_does_not_need_the_dialog_to_show(self):
        self.assertFalse(self.dialog.isVisible())
        box = self.ask()
        self.assertTrue(box.isVisible())
        box.close()

    def test_a_second_request_does_not_stack_prompts(self):
        box = self.ask()
        self.web.controlRequested.emit('abc')
        self.assertIs(self.dialog._prompts['abc'], box)
        box.close()

    def test_the_list_says_who_wants_and_who_has_control(self):
        self.viewer.control = 'requested'
        self.web.viewersChanged.emit()
        self.assertIn('wants control', self.dialog.viewers.item(0).text())
        self.viewer.control = 'granted'
        self.web.viewersChanged.emit()
        self.assertIn('controls', self.dialog.viewers.item(0).text())

    def test_the_operator_can_take_control_back(self):
        self.viewer.control = 'granted'
        self.web.viewersChanged.emit()
        self.assertFalse(self.dialog.takeBackButton.isEnabled())
        self.dialog.viewers.setCurrentRow(0)
        self.assertTrue(self.dialog.takeBackButton.isEnabled())
        self.dialog.takeBackButton.click()
        self.assertEqual(self.viewer.control, 'none')

    def test_the_window_says_what_a_tablet_may_do(self):
        self.assertIn('blacklevel', self.dialog.controlNote.text())
        self.web.controlOverHttp = False
        other = QWebShareDialog(self.web)
        self.addCleanup(other.deleteLater)
        self.assertIn('https', other.controlNote.text())
        self.assertIn('View only', other.controlNote.text())

    def test_without_a_camera_the_window_says_nothing_about_control(self):
        dialog = QWebShareDialog(QWebScreen(port=8099))
        self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog.controlNote.isHidden())


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
