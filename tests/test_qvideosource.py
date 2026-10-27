'''Unit tests for QVideoSource.'''
import subprocess
import sys
import time
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets, QtTest
from QVideo.tests.signals import record
from QVideo.lib.QVideoSource import QVideoSource
from QVideo.lib.videotypes import FrameInfo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


def make_mock_source(fps=30., width=640, height=480,
                     read_ok=True, frame=None):
    '''Return a MagicMock standing in for a QCamera or QVideoReader.'''
    if frame is None:
        frame = _FRAME.copy()
    source = MagicMock()
    source.fps = fps
    source.actualFps = fps
    source.shape = QtCore.QSize(width, height)
    source.isOpen.return_value = True
    source.saferead.return_value = (read_ok, frame)
    source.__exit__ = MagicMock(return_value=False)
    return source


def make_vs(source=None) -> QVideoSource:
    '''Return a QVideoSource wrapping a mock source.'''
    if source is None:
        source = make_mock_source()
    return QVideoSource(source)


def one_shot_source(read_ok=True):
    '''Source whose saferead() stops the loop after one call.'''
    vs_ref = [None]
    source = make_mock_source(read_ok=read_ok)

    def saferead():
        vs_ref[0]._running = False
        return (read_ok, _FRAME.copy() if read_ok else None)

    source.saferead.side_effect = saferead
    return source, vs_ref


def n_shot_source(n):
    '''Source whose saferead() stops the loop after *n* good frames.'''
    vs_ref = [None]
    source = make_mock_source()
    count = [0]

    def saferead():
        count[0] += 1
        if count[0] >= n:
            vs_ref[0]._running = False
        return True, _FRAME.copy()

    source.saferead.side_effect = saferead
    return source, vs_ref, count


class TestInit(unittest.TestCase):

    def test_source_stored(self):
        source = make_mock_source()
        vs = make_vs(source)
        self.assertIs(vs.source, source)

    def test_has_mutex(self):
        vs = make_vs()
        self.assertIsInstance(vs.mutex, QtCore.QMutex)

    def test_has_waitcondition(self):
        vs = make_vs()
        self.assertIsInstance(vs.waitcondition, QtCore.QWaitCondition)

    def test_initially_not_paused(self):
        vs = make_vs()
        self.assertFalse(vs.isPaused())

    def test_initially_running(self):
        vs = make_vs()
        self.assertTrue(vs._running)

    def test_source_moved_to_thread(self):
        source = make_mock_source()
        vs = make_vs(source)
        source.moveToThread.assert_called_once_with(vs)

    def test_shape_changed_aliased_from_source(self):
        source = make_mock_source()
        vs = make_vs(source)
        self.assertIs(vs.shapeChanged, source.shapeChanged)


class TestProperties(unittest.TestCase):

    def test_source_property(self):
        source = make_mock_source()
        vs = make_vs(source)
        self.assertIs(vs.source, source)

    def test_fps_is_the_rate_the_source_delivers(self):
        source = make_mock_source(fps=60.)
        source.actualFps = 45.
        vs = make_vs(source)
        self.assertEqual(vs.fps, 45.)

    def test_shape_delegates_to_source(self):
        source = make_mock_source(width=1280, height=720)
        vs = make_vs(source)
        self.assertEqual(vs.shape, QtCore.QSize(1280, 720))

    def test_isopen_delegates_to_source(self):
        source = make_mock_source()
        vs = make_vs(source)
        self.assertTrue(vs.isOpen())
        source.isOpen.return_value = False
        self.assertFalse(vs.isOpen())


class TestStart(unittest.TestCase):

    def test_start_returns_self(self):
        vs = make_vs()
        result = vs.start()
        vs.stop()
        vs.quit()
        vs.wait()
        self.assertIs(result, vs)


class TestStop(unittest.TestCase):

    def test_stop_sets_running_false(self):
        vs = make_vs()
        vs.stop()
        self.assertFalse(vs._running)

    def test_stop_clears_paused(self):
        vs = make_vs()
        vs._paused = True
        vs.stop()
        self.assertFalse(vs._paused)

    def test_stop_wakes_waitcondition(self):
        vs = make_vs()
        with patch.object(vs.waitcondition, 'wakeAll') as mock_wake:
            vs.stop()
        mock_wake.assert_called_once()


class TestPauseResume(unittest.TestCase):

    def test_pause_sets_paused_when_running(self):
        vs = make_vs()
        vs.pause()
        self.assertTrue(vs.isPaused())

    def test_pause_no_op_when_not_running(self):
        vs = make_vs()
        vs._running = False
        vs.pause()
        self.assertFalse(vs.isPaused())

    def test_resume_wakes_waitcondition(self):
        vs = make_vs()
        with patch.object(vs.waitcondition, 'wakeAll') as mock_wake:
            vs.resume()
        mock_wake.assert_called_once()

    def test_ispaused_reflects_state(self):
        vs = make_vs()
        self.assertFalse(vs.isPaused())
        vs.pause()
        self.assertTrue(vs.isPaused())

    def test_resume_clears_paused(self):
        vs = make_vs()
        vs.pause()
        vs.resume()
        self.assertFalse(vs.isPaused())

    def test_resume_arriving_during_a_read_is_not_lost(self):
        '''pause() then resume() while a read is in flight must not stall.'''
        source = make_mock_source()
        vs = make_vs(source)
        calls = []

        def saferead():
            calls.append(1)
            if len(calls) == 1:
                vs.pause()
                vs.resume()
            return True, _FRAME.copy()

        source.saferead.side_effect = saferead
        vs.start()
        deadline = time.monotonic() + 1.
        while len(calls) < 5 and time.monotonic() < deadline:
            QtTest.QTest.qWait(10)
        vs.stop()
        self.assertTrue(vs.wait(2000))
        self.assertGreaterEqual(len(calls), 5)


class TestSeek(unittest.TestCase):

    def test_seek_records_the_target_and_wakes_the_loop(self):
        vs = make_vs()
        with patch.object(vs.waitcondition, 'wakeAll') as mock_wake:
            vs.seek(7)
        self.assertEqual(vs._seek, 7)
        mock_wake.assert_called_once()

    def test_paused_source_delivers_one_frame_then_waits(self):
        source = make_mock_source()
        calls = []
        source.seek.side_effect = lambda n: calls.append(('seek', n))
        source.saferead.side_effect = (
            lambda: (calls.append(('read',)), (True, _FRAME.copy()))[1])
        vs = make_vs(source)
        vs.start()
        vs.pause()
        QtTest.QTest.qWait(100)
        calls.clear()
        QtTest.QTest.qWait(50)
        self.assertEqual(calls, [])
        vs.seek(4)
        deadline = time.monotonic() + 1.
        while len(calls) < 2 and time.monotonic() < deadline:
            QtTest.QTest.qWait(10)
        QtTest.QTest.qWait(50)
        self.assertEqual(calls, [('seek', 4), ('read',)])
        self.assertTrue(vs.isPaused())
        vs.stop()
        self.assertTrue(vs.wait(2000))

    def test_seek_is_consumed_once(self):
        source = make_mock_source()
        vs = make_vs(source)
        vs.seek(3)
        source.saferead.side_effect = (
            lambda: (setattr(vs, '_running', False), (True, _FRAME.copy()))[1])
        vs.run()
        source.seek.assert_called_once_with(3)
        self.assertIsNone(vs._seek)


class TestRun(unittest.TestCase):
    '''Tests for run() called directly so coverage can trace the body.

    One QThread integration test is included to verify the actual
    threading mechanism.
    '''

    def test_emits_new_frame_on_successful_read(self):
        source, ref = one_shot_source(read_ok=True)
        vs = make_vs(source)
        ref[0] = vs
        spy = record(vs.newFrame)
        vs.run()
        self.assertGreater(len(spy), 0)

    def test_does_not_emit_on_failed_read(self):
        source, ref = one_shot_source(read_ok=False)
        vs = make_vs(source)
        ref[0] = vs
        spy = record(vs.newFrame)
        vs.run()
        self.assertEqual(len(spy), 0)

    def test_emitted_frame_is_ndarray(self):
        source, ref = one_shot_source(read_ok=True)
        vs = make_vs(source)
        ref[0] = vs
        spy = record(vs.newFrame)
        vs.run()
        self.assertIsInstance(spy[0][0], np.ndarray)

    def test_emits_frame_and_info(self):
        source, ref = one_shot_source(read_ok=True)
        vs = make_vs(source)
        ref[0] = vs
        spy = record(vs.newFrame)
        vs.run()
        self.assertEqual(len(spy[0]), 2)
        self.assertIsInstance(spy[0][1], FrameInfo)

    def test_frame_index_counts_from_zero(self):
        source, ref, _ = n_shot_source(3)
        vs = make_vs(source)
        ref[0] = vs
        spy = record(vs.newFrame)
        vs.run()
        self.assertEqual([args[1].index for args in spy], [0, 1, 2])

    def test_failed_reads_do_not_consume_indices(self):
        source = make_mock_source()
        vs = make_vs(source)
        results = iter([(False, None), (True, _FRAME.copy()),
                        (False, None), (True, _FRAME.copy())])

        def saferead():
            ok, frame = next(results)
            if ok and vs._frames == 1:
                vs._running = False
            return ok, frame
        source.saferead.side_effect = saferead
        spy = record(vs.newFrame)
        vs.run()
        self.assertEqual([args[1].index for args in spy], [0, 1])

    def test_index_restarts_on_each_run(self):
        source, ref, count = n_shot_source(2)
        vs = make_vs(source)
        ref[0] = vs
        vs.run()
        count[0] = 0
        vs._running = True
        spy = record(vs.newFrame)
        vs.run()
        self.assertEqual(spy[0][1].index, 0)

    def test_timestamps_are_monotonic_and_taken_after_read(self):
        source, ref, _ = n_shot_source(3)
        vs = make_vs(source)
        ref[0] = vs
        spy = record(vs.newFrame)
        before = time.perf_counter()
        vs.run()
        after = time.perf_counter()
        stamps = [args[1].timestamp for args in spy]
        self.assertEqual(stamps, sorted(stamps))
        self.assertGreaterEqual(stamps[0], before)
        self.assertLessEqual(stamps[-1], after)

    def test_hardware_timestamp_is_none_by_default(self):
        source, ref = one_shot_source(read_ok=True)
        vs = make_vs(source)
        ref[0] = vs
        spy = record(vs.newFrame)
        vs.run()
        self.assertIsNone(spy[0][1].hardware_timestamp)

    def test_opens_and_closes_source(self):
        source = make_mock_source()
        vs = make_vs(source)
        vs._running = False   # exit immediately without reading
        vs.run()
        source.__enter__.assert_called_once()
        source.__exit__.assert_called_once()

    def test_exits_when_stopped_while_paused(self):
        source = make_mock_source()
        vs = make_vs(source)
        vs._paused = True

        def mock_wait(mutex):
            vs._paused = False
            vs._running = False

        with patch.object(vs.waitcondition, 'wait', side_effect=mock_wait):
            vs.run()

        self.assertFalse(vs._running)

    def test_thread_stops_cleanly(self):
        '''Integration test: verify run() stops when stop() is called from
        another thread.'''
        vs = make_vs()
        vs.start()
        vs.stop()
        vs.quit()
        finished = vs.wait(2000)
        self.assertTrue(finished)


class TestDroppingARunningSource(unittest.TestCase):

    CODE = """
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import gc
from qtpy import QtWidgets
app = QtWidgets.QApplication([])
from QVideo.cameras.Noise import QNoiseCamera
from QVideo.lib import QVideoSource


def build():
    source = QVideoSource(QNoiseCamera()).start()
    assert source.isRunning()


build()
gc.collect()
print('survived')
"""

    def test_dropping_a_running_source_is_safe(self):
        result = subprocess.run([sys.executable, '-c', self.CODE],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        self.assertIn('survived', result.stdout)
        self.assertNotIn('Destroyed while thread', result.stderr)

    def test_finalizer_leaves_an_unstarted_source_alone(self):
        vs = make_vs()
        with patch.object(vs, 'stop') as stop:
            vs.__del__()
        stop.assert_not_called()

    def test_finalizer_ignores_a_deleted_thread(self):
        vs = make_vs()
        with patch.object(QVideoSource, 'isRunning',
                          side_effect=RuntimeError):
            vs.__del__()


if __name__ == '__main__':
    unittest.main()
