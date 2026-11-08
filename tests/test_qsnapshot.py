'''Unit tests for QSnapshot.'''
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
import numpy as np
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib.QSnapshot import QSnapshot
from QVideo.lib.QVideoScreen import QVideoScreen
from QVideo.lib.videotypes import FrameInfo
from QVideo.tests.signals import record


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_parent():
    return QtWidgets.QWidget()


def make_snapshot(key='Ctrl+Shift+S'):
    return QSnapshot(make_parent(), key=key)


def gray_frame(h=4, w=6):
    return np.zeros((h, w), dtype=np.uint8)


def rgb_frame(h=4, w=6):
    return np.zeros((h, w, 3), dtype=np.uint8)


def rgba_frame(h=4, w=6):
    return np.zeros((h, w, 4), dtype=np.uint8)


class TestInit(unittest.TestCase):

    def test_creates_successfully(self):
        self.assertIsInstance(make_snapshot(), QSnapshot)

    def test_frame_initially_none(self):
        self.assertIsNone(make_snapshot()._frame)

    def test_custom_key_accepted(self):
        snap = QSnapshot(make_parent(), key='F12')
        self.assertIsInstance(snap, QSnapshot)

    def test_custom_key_as_accepted(self):
        snap = QSnapshot(make_parent(), key_as='F11')
        self.assertIsInstance(snap, QSnapshot)

    def test_parent_is_set(self):
        parent = make_parent()
        snap = QSnapshot(parent)
        self.assertIs(snap.parent(), parent)

    def test_shortcuts_use_widget_with_children_context(self):
        parent = make_parent()
        QSnapshot(parent)
        shortcuts = parent.findChildren(QtWidgets.QShortcut)
        self.assertTrue(len(shortcuts) >= 2)
        for sc in shortcuts:
            self.assertEqual(
                sc.context(),
                QtCore.Qt.WidgetWithChildrenShortcut)


class TestNewFrame(unittest.TestCase):

    def test_stores_frame(self):
        snap = make_snapshot()
        frame = gray_frame()
        snap.newFrame(frame)
        self.assertIs(snap._frame, frame)

    def test_overwrites_previous_frame(self):
        snap = make_snapshot()
        snap.newFrame(gray_frame())
        frame2 = rgb_frame()
        snap.newFrame(frame2)
        self.assertIs(snap._frame, frame2)


class TestSnap(unittest.TestCase):

    def test_snap_with_no_frame_logs_warning(self):
        snap = make_snapshot()
        with self.assertLogs('QVideo.lib.QSnapshot', level='WARNING'):
            snap.snap()

    def test_snap_saves_the_frame_and_its_levels(self):
        snap = make_snapshot()
        frame = gray_frame()
        snap.newFrame(frame, FrameInfo(0, 0., levels=(0., 4095.)))
        with patch.object(snap.saver, 'save') as save:
            snap.snap()
        save.assert_called_once_with(frame, levels=(0., 4095.))

    def test_the_name_is_made_by_the_saver_in_the_home_directory(self):
        snap = make_snapshot()
        self.assertEqual(snap.saver.directory, Path.home())
        self.assertEqual(snap.saver.prefix, 'snapshot')

    def snapTo(self, folder):
        parent = make_parent()
        snap = QSnapshot(parent)
        snap.saver.directory = Path(folder)
        snap.newFrame(gray_frame())
        messages = record(snap.saver.message)
        snap.snap()
        return messages

    def test_snap_writes_a_file(self):
        with tempfile.TemporaryDirectory() as folder:
            self.snapTo(folder)
            self.assertEqual(len(list(Path(folder).glob('snapshot_*.png'))),
                             1)

    def test_the_saver_reports_to_message(self):
        with tempfile.TemporaryDirectory() as folder:
            messages = self.snapTo(folder)
        self.assertTrue(messages[0][0].startswith('Saved '))


class TestSnapAs(unittest.TestCase):

    def test_snapas_with_no_frame_logs_warning(self):
        snap = make_snapshot()
        with self.assertLogs('QVideo.lib.QSnapshot', level='WARNING'):
            snap.snapAs()

    def test_snapas_asks_the_saver_for_a_dialog(self):
        snap = make_snapshot()
        frame = gray_frame()
        snap.newFrame(frame)
        with patch.object(snap.saver, 'save') as save:
            snap.snapAs()
        save.assert_called_once_with(frame, ask=True, levels=None)


class TestScreenshot(unittest.TestCase):

    def setUp(self):
        self.parent = make_parent()
        self.screen = QVideoScreen(self.parent)
        self.snap = QSnapshot(self.parent, screen=self.screen)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.snap.saver.directory = self.folder
        self.picture = np.zeros((4, 6, 3), np.uint8)

    def test_the_shortcuts_exist_only_with_a_screen(self):
        keys = {sc.key().toString() for sc in
                self.parent.findChildren(QtWidgets.QShortcut)}
        for key in ('Ctrl+Shift+P', 'Ctrl+Shift+Alt+P'):
            self.assertIn(QtGui.QKeySequence(key).toString(), keys)
        bare = make_parent()
        QSnapshot(bare)
        self.assertEqual(len(bare.findChildren(QtWidgets.QShortcut)), 2)

    def test_the_keys_can_be_chosen(self):
        parent = make_parent()
        QSnapshot(parent, screen=QVideoScreen(parent), key_screen='F9',
                  key_screen_as='F10')
        keys = {sc.key().toString() for sc in
                parent.findChildren(QtWidgets.QShortcut)}
        self.assertLessEqual({'F9', 'F10'}, keys)

    def test_screenshot_saves_what_the_screen_shows(self):
        messages = record(self.snap.saver.message)
        with patch.object(self.screen, 'screenshot',
                          return_value=self.picture):
            self.snap.screenshot()
        files = list(self.folder.glob('screenshot_*.png'))
        self.assertEqual(len(files), 1)
        self.assertTrue(messages[0][0].startswith('Saved '))

    def test_screenshotas_asks_for_a_name(self):
        with patch.object(self.screen, 'screenshot',
                          return_value=self.picture), \
                patch.object(self.snap.saver, 'save') as save:
            self.snap.screenshotAs()
        save.assert_called_once_with(self.picture, ask=True,
                                     prefix='screenshot')

    def test_a_screen_without_size_saves_nothing(self):
        with patch.object(self.screen, 'screenshot',
                          return_value=np.empty((0, 0, 3), np.uint8)):
            with self.assertLogs('QVideo.lib.QSnapshot', 'WARNING'):
                self.snap.screenshot()
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_without_a_screen_it_warns(self):
        snap = make_snapshot()
        with self.assertLogs('QVideo.lib.QSnapshot', 'WARNING'):
            snap.screenshot()

    def test_the_real_screen_gives_a_picture(self):
        self.screen.resize(64, 48)
        self.screen.show()
        app.processEvents()
        self.snap.screenshot()
        self.assertEqual(len(list(self.folder.glob('screenshot_*.png'))), 1)


if __name__ == '__main__':
    unittest.main()
