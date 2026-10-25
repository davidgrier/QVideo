'''Unit tests for AsyncVideoFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import VideoFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((4, 4), dtype=np.uint8)
_RESULT = np.ones((4, 4), dtype=np.uint8) * 42


def make_filter() -> AsyncVideoFilter:
    '''Create an AsyncVideoFilter with threading patched to be synchronous.

    Patching moveToThread keeps the worker on the GUI thread, making the
    _submit signal connection Direct so that process() runs synchronously
    in add(), allowing tests to inspect results without waiting.
    '''
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return AsyncVideoFilter()


class TestAsyncVideoFilterInit(unittest.TestCase):

    def test_is_videofilter(self):
        f = make_filter()
        self.assertIsInstance(f, VideoFilter)

    def test_initial_data_none(self):
        f = make_filter()
        self.assertIsNone(f.data)


class TestAsyncVideoFilterProcess(unittest.TestCase):

    def test_process_is_passthrough_by_default(self):
        f = make_filter()
        result = f.process(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)


class TestAsyncVideoFilterGet(unittest.TestCase):

    def test_get_returns_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.get())

    def test_get_returns_raw_frame_when_result_pending(self):
        f = make_filter()
        f._ready = False       # suppress submission
        f.add(_FRAME)
        # _result is still None → passthrough
        np.testing.assert_array_equal(f.get(), _FRAME)

    def test_get_returns_cached_result_after_process(self):
        f = make_filter()
        f._result = _RESULT
        np.testing.assert_array_equal(f.get(), _RESULT)

    def test_get_prefers_result_over_raw_frame(self):
        f = make_filter()
        f._ready = False
        f.add(_FRAME)
        f._result = _RESULT
        np.testing.assert_array_equal(f.get(), _RESULT)


class TestAsyncVideoFilterAdd(unittest.TestCase):

    def test_add_caches_raw_frame(self):
        f = make_filter()
        f.add(_FRAME)
        np.testing.assert_array_equal(f.data, _FRAME)

    def test_add_drops_frame_when_not_ready(self):
        f = make_filter()
        f._ready = False
        submitted = []
        f._submit.connect(lambda img: submitted.append(img))
        f.add(_FRAME)
        self.assertEqual(len(submitted), 0)

    def test_add_submits_when_ready(self):
        f = make_filter()
        submitted = []
        f._submit.connect(lambda img: submitted.append(img))
        f.add(_FRAME)
        self.assertGreater(len(submitted), 0)


class TestAsyncVideoFilterCall(unittest.TestCase):

    def test_call_returns_result_synchronously(self):
        '''With threading patched to direct connections, __call__ is synchronous.'''
        f = make_filter()
        result = f(_FRAME)
        # Default process is passthrough, so result == _FRAME
        np.testing.assert_array_equal(result, _FRAME)


class _FlakyFilter(AsyncVideoFilter):
    '''Filter whose process() raises for frames filled with 255.'''

    def process(self, image):
        if image.max() == 255:
            raise ValueError('cannot process this frame')
        return image * 2


def make_flaky() -> _FlakyFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return _FlakyFilter()


_GOOD = np.full((4, 4), 3, dtype=np.uint8)
_BAD = np.full((4, 4), 255, dtype=np.uint8)


class TestAsyncVideoFilterFailure(unittest.TestCase):
    '''A process() that raises must not leave the filter stuck, and the
    error must reach the consumer rather than disappear in the worker.'''

    def test_get_reraises_the_process_error(self):
        f = make_flaky()
        f.add(_BAD)
        with self.assertRaises(ValueError):
            f.get()

    def test_calling_the_filter_raises_the_error_to_the_caller(self):
        f = make_flaky()
        with self.assertRaises(ValueError):
            f(_BAD)

    def test_the_error_is_raised_only_once(self):
        f = make_flaky()
        f.add(_BAD)
        with self.assertRaises(ValueError):
            f.get()
        np.testing.assert_array_equal(f.get(), _BAD)    # raw passthrough

    def test_filter_accepts_frames_after_a_failure(self):
        f = make_flaky()
        f.add(_BAD)
        self.assertTrue(f._ready)

    def test_next_frame_is_processed_after_a_failure(self):
        f = make_flaky()
        f.add(_BAD)
        with self.assertRaises(ValueError):
            f.get()
        f.add(_GOOD)
        np.testing.assert_array_equal(f.get(), _GOOD * 2)

    def test_a_failure_does_not_escape_the_worker(self):
        f = make_flaky()
        f.add(_BAD)          # would raise here if the worker let it escape


class TestAsyncVideoFilterCleanup(unittest.TestCase):

    def setUp(self):
        self._p_start = patch.object(QtCore.QThread, 'start')
        self._p_move = patch.object(QtCore.QObject, 'moveToThread')
        self._p_start.start()
        self._p_move.start()

    def tearDown(self):
        self._p_start.stop()
        self._p_move.stop()

    def test_cleanup_quits_thread(self):
        f = AsyncVideoFilter()
        with patch.object(f._thread, 'isRunning', return_value=True), \
             patch.object(f._thread, 'quit') as mock_quit, \
             patch.object(f._thread, 'wait'):
            f._cleanup()
        mock_quit.assert_called_once()

    def test_cleanup_waits_for_thread(self):
        f = AsyncVideoFilter()
        with patch.object(f._thread, 'isRunning', return_value=True), \
             patch.object(f._thread, 'quit'), \
             patch.object(f._thread, 'wait') as mock_wait:
            f._cleanup()
        mock_wait.assert_called_once()

    def test_cleanup_is_idempotent_when_thread_not_running(self):
        f = AsyncVideoFilter()
        with patch.object(f._thread, 'isRunning', return_value=False), \
             patch.object(f._thread, 'quit') as mock_quit:
            f._cleanup()
            f._cleanup()
        mock_quit.assert_not_called()

    def test_destroyed_connected_to_cleanup(self):
        f = AsyncVideoFilter()
        try:
            f.destroyed.disconnect(f._cleanup)
        except RuntimeError:
            self.fail('_cleanup was not connected to destroyed')

    def test_abouttoquit_connected_to_cleanup(self):
        f = AsyncVideoFilter()
        app = QtCore.QCoreApplication.instance()
        try:
            app.aboutToQuit.disconnect(f._cleanup)
        except RuntimeError:
            self.fail('_cleanup was not connected to aboutToQuit')

    def test_no_connection_when_no_app(self):
        with patch.object(QtCore.QCoreApplication, 'instance', return_value=None):
            f = AsyncVideoFilter()
        app = QtCore.QCoreApplication.instance()
        with self.assertRaises((RuntimeError, TypeError)):
            app.aboutToQuit.disconnect(f._cleanup)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
