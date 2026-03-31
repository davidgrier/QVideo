'''Unit tests for QVideoSource.'''
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets, QtTest
from QVideo.lib.QVideoSource import QVideoSource


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


def make_mock_source(fps=30., width=640, height=480,
                     read_ok=True, frame=None):
    '''Return a MagicMock standing in for a QCamera or QVideoReader.'''
    if frame is None:
        frame = _FRAME.copy()
    source = MagicMock()
    source.fps = fps
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

    def test_fps_delegates_to_source(self):
        source = make_mock_source(fps=60.)
        vs = make_vs(source)
        self.assertEqual(vs.fps, 60.)

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


class TestRun(unittest.TestCase):
    '''Tests for run() called directly so coverage can trace the body.

    One QThread integration test is included to verify the actual
    threading mechanism.
    '''

    def test_emits_new_frame_on_successful_read(self):
        source, ref = one_shot_source(read_ok=True)
        vs = make_vs(source)
        ref[0] = vs
        spy = QtTest.QSignalSpy(vs.newFrame)
        vs.run()
        self.assertGreater(len(spy), 0)

    def test_does_not_emit_on_failed_read(self):
        source, ref = one_shot_source(read_ok=False)
        vs = make_vs(source)
        ref[0] = vs
        spy = QtTest.QSignalSpy(vs.newFrame)
        vs.run()
        self.assertEqual(len(spy), 0)

    def test_emitted_frame_is_ndarray(self):
        source, ref = one_shot_source(read_ok=True)
        vs = make_vs(source)
        ref[0] = vs
        spy = QtTest.QSignalSpy(vs.newFrame)
        vs.run()
        self.assertIsInstance(spy[0][0], np.ndarray)

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


if __name__ == '__main__':
    unittest.main()
