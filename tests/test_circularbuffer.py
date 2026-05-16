'''Unit tests for dvr.QCircularBuffer.'''
import sys
import unittest
from unittest.mock import patch, MagicMock
from collections import deque
import numpy as np
from qtpy import QtWidgets

from QVideo.dvr.QCircularBuffer import QCircularBuffer

_module = sys.modules['QVideo.dvr.QCircularBuffer']


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_frame(h=4, w=4):
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestConstruction(unittest.TestCase):

    def test_default_construction(self):
        buf = QCircularBuffer()
        self.assertIsInstance(buf, QCircularBuffer)

    def test_default_fps(self):
        buf = QCircularBuffer()
        self.assertEqual(buf.fps, 24.)

    def test_default_duration(self):
        buf = QCircularBuffer()
        self.assertEqual(buf.duration, 5)

    def test_custom_fps(self):
        buf = QCircularBuffer(fps=30.)
        self.assertEqual(buf.fps, 30.)

    def test_custom_duration(self):
        buf = QCircularBuffer(duration=10)
        self.assertEqual(buf.duration, 10)

    def test_initial_length_is_zero(self):
        buf = QCircularBuffer()
        self.assertEqual(len(buf), 0)


class TestFpsProperty(unittest.TestCase):

    def test_set_fps(self):
        buf = QCircularBuffer(fps=24.)
        buf.fps = 60.
        self.assertEqual(buf.fps, 60.)

    def test_fps_change_resizes_buffer(self):
        buf = QCircularBuffer(fps=10., duration=2)
        buf.fps = 20.
        # maxlen should now be 40
        self.assertEqual(buf._buffer.maxlen, 40)

    def test_fps_change_preserves_frames(self):
        buf = QCircularBuffer(fps=10., duration=5)
        frame = make_frame()
        for _ in range(5):
            buf.append(frame)
        buf.fps = 20.
        self.assertEqual(len(buf), 5)


class TestDurationProperty(unittest.TestCase):

    def test_set_duration(self):
        buf = QCircularBuffer()
        buf.duration = 10
        self.assertEqual(buf.duration, 10)

    def test_duration_minimum_is_one(self):
        buf = QCircularBuffer()
        buf.duration = 0
        self.assertEqual(buf.duration, 1)

    def test_duration_change_resizes_buffer(self):
        buf = QCircularBuffer(fps=10., duration=2)
        buf.duration = 3
        self.assertEqual(buf._buffer.maxlen, 30)

    def test_duration_change_trims_oldest_frames(self):
        buf = QCircularBuffer(fps=1., duration=10)
        frame = make_frame()
        for _ in range(10):
            buf.append(frame)
        buf.duration = 3
        self.assertEqual(len(buf), 3)


class TestClear(unittest.TestCase):

    def test_clear_empties_buffer(self):
        buf = QCircularBuffer()
        buf.append(make_frame())
        buf.clear()
        self.assertEqual(len(buf), 0)


class TestAppend(unittest.TestCase):

    def test_append_increments_length(self):
        buf = QCircularBuffer()
        buf.append(make_frame())
        self.assertEqual(len(buf), 1)

    def test_append_stores_frame_and_timestamp(self):
        buf = QCircularBuffer()
        frame = make_frame()
        buf.append(frame)
        ts, stored = buf._buffer[0]
        self.assertIsInstance(ts, float)
        np.testing.assert_array_equal(stored, frame)

    def test_buffer_wraps_at_maxlen(self):
        buf = QCircularBuffer(fps=5., duration=1)
        frame = make_frame()
        for _ in range(10):
            buf.append(frame)
        self.assertEqual(len(buf), 5)


class TestSaveEmpty(unittest.TestCase):

    def test_save_returns_false_when_empty(self):
        buf = QCircularBuffer()
        self.assertFalse(buf.save('out.mkv'))


class TestSaveOpenCV(unittest.TestCase):

    def _fill(self, buf, n=3):
        frame = make_frame()
        for _ in range(n):
            buf.append(frame)

    def test_save_mkv_calls_writer(self):
        buf = QCircularBuffer(fps=10., duration=5)
        self._fill(buf)
        mock_writer = MagicMock()
        mock_writer.open.return_value = True
        with patch.object(_module, 'QOpenCVWriter', return_value=mock_writer):
            result = buf.save('out.mkv')
        self.assertTrue(result)
        mock_writer.open.assert_called_once()
        self.assertEqual(mock_writer._write.call_count, 3)
        mock_writer.close.assert_called_once()

    def test_save_returns_false_when_writer_fails_to_open(self):
        buf = QCircularBuffer(fps=10., duration=5)
        self._fill(buf)
        mock_writer = MagicMock()
        mock_writer.open.return_value = False
        with patch.object(_module, 'QOpenCVWriter', return_value=mock_writer):
            result = buf.save('out.mkv')
        self.assertFalse(result)


class TestSaveHDF5(unittest.TestCase):

    def _fill(self, buf, n=3):
        frame = make_frame()
        for _ in range(n):
            buf.append(frame)

    def test_save_h5_writes_datasets(self):
        buf = QCircularBuffer(fps=10., duration=5)
        self._fill(buf)
        mock_h5py = MagicMock()
        mock_file = MagicMock()
        mock_grp = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.create_group.return_value = mock_grp
        mock_h5py.File.return_value = mock_file
        with patch.dict('sys.modules', {'h5py': mock_h5py}):
            result = buf.save('out.h5')
        self.assertTrue(result)
        mock_grp.create_dataset.assert_called()

    def test_save_h5_returns_false_on_oserror(self):
        buf = QCircularBuffer(fps=10., duration=5)
        self._fill(buf)
        mock_h5py = MagicMock()
        mock_h5py.File.side_effect = OSError('disk full')
        with patch.dict('sys.modules', {'h5py': mock_h5py}):
            result = buf.save('out.h5')
        self.assertFalse(result)

    def test_save_h5_missing_h5py_returns_false(self):
        buf = QCircularBuffer(fps=10., duration=5)
        self._fill(buf)
        with patch.dict('sys.modules', {'h5py': None}):
            result = buf.save('out.h5')
        self.assertFalse(result)


class TestActualFps(unittest.TestCase):

    def test_single_frame_returns_nominal_fps(self):
        buf = QCircularBuffer(fps=30.)
        buf.append(make_frame())
        items = list(buf._buffer)
        self.assertEqual(buf._actualFps(items), 30.)

    def test_two_frames_computes_fps(self):
        buf = QCircularBuffer(fps=30.)
        items = [(0.0, make_frame()), (1.0, make_frame())]
        fps = buf._actualFps(items)
        self.assertAlmostEqual(fps, 1.0)

    def test_zero_elapsed_returns_nominal_fps(self):
        buf = QCircularBuffer(fps=30.)
        frame = make_frame()
        items = [(0.0, frame), (0.0, frame)]
        self.assertEqual(buf._actualFps(items), 30.)


if __name__ == '__main__':
    unittest.main()
