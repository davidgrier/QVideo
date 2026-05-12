'''Unit tests for QSnapshot.'''
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
import os
import numpy as np
from qtpy import QtWidgets, QtGui
from QVideo.lib.QSnapshot import QSnapshot


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

    def test_snap_calls_save_with_frame(self):
        snap = make_snapshot()
        frame = gray_frame()
        snap.newFrame(frame)
        with patch.object(snap, '_save') as mock_save:
            snap.snap()
        mock_save.assert_called_once()
        self.assertIs(mock_save.call_args[0][0], frame)

    def test_snap_filename_contains_snapshot(self):
        snap = make_snapshot()
        snap.newFrame(gray_frame())
        with patch.object(snap, '_save') as mock_save:
            snap.snap()
        filename = mock_save.call_args[0][1]
        self.assertIn('snapshot', filename)

    def test_snap_filename_ends_with_png(self):
        snap = make_snapshot()
        snap.newFrame(gray_frame())
        with patch.object(snap, '_save') as mock_save:
            snap.snap()
        filename = mock_save.call_args[0][1]
        self.assertTrue(filename.endswith('.png'))

    def test_snap_filename_contains_timestamp(self):
        snap = make_snapshot()
        snap.newFrame(gray_frame())
        with patch.object(snap, '_save') as mock_save:
            with patch('datetime.datetime') as mock_dt:
                mock_dt.now.return_value.strftime.return_value = '20260511_120000'
                snap.snap()
        filename = mock_save.call_args[0][1]
        self.assertIn('20260511_120000', filename)

    def test_snap_saves_to_home_directory(self):
        snap = make_snapshot()
        snap.newFrame(gray_frame())
        with patch.object(snap, '_save') as mock_save:
            snap.snap()
        filename = mock_save.call_args[0][1]
        self.assertTrue(filename.startswith(str(Path.home())))


class TestSnapAs(unittest.TestCase):

    def test_snapas_with_no_frame_logs_warning(self):
        snap = make_snapshot()
        with self.assertLogs('QVideo.lib.QSnapshot', level='WARNING'):
            snap.snapAs()

    def test_snapas_calls_save_when_filename_chosen(self):
        snap = make_snapshot()
        snap.newFrame(gray_frame())
        with patch('qtpy.QtWidgets.QFileDialog.getSaveFileName',
                   return_value=('/tmp/test.png', 'PNG Images (*.png)')):
            with patch.object(snap, '_save') as mock_save:
                snap.snapAs()
        mock_save.assert_called_once()
        self.assertEqual(mock_save.call_args[0][1], '/tmp/test.png')

    def test_snapas_prefills_default_path(self):
        snap = make_snapshot()
        snap.newFrame(gray_frame())
        default = snap._defaultPath()
        with patch('qtpy.QtWidgets.QFileDialog.getSaveFileName',
                   return_value=('', '')) as mock_dialog:
            snap.snapAs()
        initial_path = mock_dialog.call_args[0][2]
        self.assertTrue(initial_path.startswith(str(Path.home())))
        self.assertIn('snapshot', initial_path)

    def test_snapas_does_not_save_when_dialog_cancelled(self):
        snap = make_snapshot()
        snap.newFrame(gray_frame())
        with patch('qtpy.QtWidgets.QFileDialog.getSaveFileName',
                   return_value=('', '')):
            with patch.object(snap, '_save') as mock_save:
                snap.snapAs()
        mock_save.assert_not_called()


class TestSave(unittest.TestCase):

    def _save_to_tmp(self, frame, suffix='.png'):
        snap = make_snapshot()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            path = f.name
        try:
            snap._save(frame, path)
            return path
        except Exception:
            os.unlink(path)
            raise

    def test_saves_grayscale_frame(self):
        path = self._save_to_tmp(gray_frame())
        self.assertGreater(os.path.getsize(path), 0)
        os.unlink(path)

    def test_saves_rgb_frame(self):
        path = self._save_to_tmp(rgb_frame())
        self.assertGreater(os.path.getsize(path), 0)
        os.unlink(path)

    def test_saves_rgba_frame(self):
        path = self._save_to_tmp(rgba_frame())
        self.assertGreater(os.path.getsize(path), 0)
        os.unlink(path)

    def test_unsupported_dtype_logs_warning(self):
        snap = make_snapshot()
        frame = np.zeros((4, 6), dtype=np.uint16)
        with self.assertLogs('QVideo.lib.QSnapshot', level='WARNING'):
            snap._save(frame, '/tmp/unused.png')

    def test_unsupported_shape_logs_warning(self):
        snap = make_snapshot()
        frame = np.zeros((4, 6, 2), dtype=np.uint8)
        with self.assertLogs('QVideo.lib.QSnapshot', level='WARNING'):
            snap._save(frame, '/tmp/unused.png')

    def test_failed_save_logs_warning(self):
        snap = make_snapshot()
        frame = gray_frame()
        with patch('qtpy.QtGui.QImage.save', return_value=False):
            with self.assertLogs('QVideo.lib.QSnapshot', level='WARNING'):
                snap._save(frame, '/tmp/unused.png')

    def test_successful_save_logs_info(self):
        snap = make_snapshot()
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            path = f.name
        try:
            with self.assertLogs('QVideo.lib.QSnapshot', level='INFO'):
                snap._save(gray_frame(), path)
        finally:
            os.unlink(path)

    def test_grayscale_content_roundtrip(self):
        frame = np.arange(24, dtype=np.uint8).reshape(4, 6)
        path = self._save_to_tmp(frame)
        loaded = QtGui.QImage(path)
        self.assertEqual(loaded.width(), 6)
        self.assertEqual(loaded.height(), 4)
        os.unlink(path)


if __name__ == '__main__':
    unittest.main()
