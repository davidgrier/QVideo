'''Unit tests for dvr.QCircularBuffer.'''
import sys
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from qtpy import QtWidgets

from QVideo.dvr.QCircularBuffer import QCircularBuffer
from QVideo.lib.videotypes import FrameInfo

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

    def test_append_stores_the_frame_with_its_information(self):
        buf = QCircularBuffer()
        frame = make_frame()
        info = FrameInfo(7, 5.0)
        buf.append(frame, info)
        stored, stored_info = buf.frames()[0]
        np.testing.assert_array_equal(stored, frame)
        self.assertIs(stored_info, info)

    def test_append_makes_the_information_that_is_missing(self):
        buf = QCircularBuffer()
        buf.append(make_frame())
        buf.append(make_frame())
        (_, first), (_, second) = buf.frames()
        self.assertIsInstance(first, FrameInfo)
        self.assertEqual((first.index, second.index), (0, 1))
        self.assertLessEqual(first.timestamp, second.timestamp)

    def test_append_accepts_a_one_argument_signal(self):
        from qtpy import QtCore

        class Emitter(QtCore.QObject):
            newFrame = QtCore.Signal(np.ndarray)
        buf = QCircularBuffer()
        e = Emitter()
        e.newFrame.connect(buf.append)
        e.newFrame.emit(make_frame())
        self.assertEqual(len(buf), 1)

    def test_buffer_wraps_at_maxlen(self):
        buf = QCircularBuffer(fps=5., duration=1)
        frame = make_frame()
        for _ in range(10):
            buf.append(frame)
        self.assertEqual(len(buf), 5)


class TestFrames(unittest.TestCase):

    def test_an_empty_buffer_has_no_frames(self):
        self.assertEqual(QCircularBuffer().frames(), [])

    def test_the_oldest_frame_comes_first(self):
        buf = QCircularBuffer()
        for i in range(3):
            buf.append(make_frame(), FrameInfo(i, float(i)))
        self.assertEqual([info.index for _, info in buf.frames()], [0, 1, 2])

    def test_the_oldest_frames_are_dropped_when_full(self):
        buf = QCircularBuffer(fps=2., duration=1)
        for i in range(5):
            buf.append(make_frame(), FrameInfo(i, float(i)))
        self.assertEqual([info.index for _, info in buf.frames()], [3, 4])

    def test_the_list_is_a_copy(self):
        buf = QCircularBuffer()
        buf.append(make_frame())
        buf.frames().clear()
        self.assertEqual(len(buf), 1)


class TestActualFps(unittest.TestCase):

    def fill(self, buf, times):
        for i, t in enumerate(times):
            buf.append(make_frame(), FrameInfo(i, t))

    def test_an_empty_buffer_returns_nominal_fps(self):
        self.assertEqual(QCircularBuffer(fps=30.).actualFps, 30.)

    def test_single_frame_returns_nominal_fps(self):
        buf = QCircularBuffer(fps=30.)
        self.fill(buf, [4.0])
        self.assertEqual(buf.actualFps, 30.)

    def test_the_rate_follows_the_capture_times(self):
        buf = QCircularBuffer(fps=30.)
        self.fill(buf, [10.0, 10.5, 11.0, 11.5, 12.0])
        self.assertAlmostEqual(buf.actualFps, 2.0)

    def test_zero_elapsed_returns_nominal_fps(self):
        buf = QCircularBuffer(fps=30.)
        self.fill(buf, [3.0, 3.0])
        self.assertEqual(buf.actualFps, 30.)


class TestTotalRAM(unittest.TestCase):

    def test_returns_int(self):
        result = QCircularBuffer._totalRAM()
        self.assertIsInstance(result, int)

    def test_reads_total_from_psutil(self):
        mock_psutil = MagicMock()
        mock_psutil.virtual_memory.return_value.total = 16 * 1024 ** 3
        with patch.object(_module, 'psutil', mock_psutil):
            result = QCircularBuffer._totalRAM()
        self.assertEqual(result, 16 * 1024 ** 3)


class TestMemoryWarning(unittest.TestCase):

    def _big_frame(self):
        # 1 GB / 10 frames → each frame is 100 MB when maxlen=10
        # makes estimated = 1 GB which is >25% of a 1 GB total
        n = (1024 ** 3) // 10
        return np.zeros(n, dtype=np.uint8)

    def test_warning_logged_when_over_threshold(self):
        buf = QCircularBuffer(fps=10., duration=1)  # maxlen=10
        with patch.object(buf, '_totalRAM', return_value=1024 ** 3):
            with self.assertLogs('QVideo.dvr.QCircularBuffer', level='WARNING') as cm:
                buf.append(self._big_frame())
        self.assertTrue(any('Circular buffer' in line for line in cm.output))

    def test_no_warning_when_under_threshold(self):
        buf = QCircularBuffer(fps=1., duration=1)  # maxlen=1, frame=48 bytes
        with patch.object(buf, '_totalRAM', return_value=1024 ** 3):
            # 48 bytes << 25% of 1 GB — no warning
            try:
                with self.assertLogs('QVideo.dvr.QCircularBuffer', level='WARNING'):
                    buf.append(make_frame())
                warned = True
            except AssertionError:
                warned = False
        self.assertFalse(warned)

    def test_warning_fires_only_once_per_resize(self):
        buf = QCircularBuffer(fps=10., duration=1)
        with patch.object(buf, '_totalRAM', return_value=1024 ** 3):
            with self.assertLogs('QVideo.dvr.QCircularBuffer', level='WARNING') as cm:
                buf.append(self._big_frame())
                buf.append(self._big_frame())
        self.assertEqual(sum(1 for line in cm.output if 'Circular buffer' in line), 1)

    def test_resize_resets_warned_flag(self):
        buf = QCircularBuffer(fps=10., duration=1)
        with patch.object(buf, '_totalRAM', return_value=1024 ** 3):
            with self.assertLogs('QVideo.dvr.QCircularBuffer', level='WARNING'):
                buf.append(self._big_frame())
            self.assertTrue(buf._warned)
            buf.duration = 2  # triggers _resize, resets _warned
            self.assertFalse(buf._warned)


if __name__ == '__main__':
    unittest.main()
