'''Unit tests for QVideoReader.'''
import unittest
import numpy as np
from unittest.mock import patch
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
from QVideo.lib.QVideoReader import QVideoReader


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640), dtype=np.uint8)


class _FakeVideoReader(QVideoReader):
    '''Minimal concrete QVideoReader for testing.'''

    def __init__(self, filename='test.avi', initialize_ok=True):
        self._width = 640
        self._height = 480
        self._fps = 30.
        self._length = 100
        self._framenumber = 0
        self._initialize_called = 0
        self._deinitialize_called = 0
        self._initialize_ok = initialize_ok
        super().__init__(filename)

    def _initialize(self) -> bool:
        self._initialize_called += 1
        return self._initialize_ok

    def _deinitialize(self) -> None:
        self._deinitialize_called += 1

    def read(self):
        self._framenumber += 1
        return True, _FRAME.copy()

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def length(self) -> int:
        return self._length

    @property
    def framenumber(self) -> int:
        return self._framenumber

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def seek(self, framenumber: int) -> None:
        self._framenumber = framenumber


def make_reader(filename='test.avi', initialize_ok=True) -> _FakeVideoReader:
    if initialize_ok:
        return _FakeVideoReader(filename=filename, initialize_ok=True)
    with assertLogs_context():
        return _FakeVideoReader(filename=filename, initialize_ok=False)


class assertLogs_context:
    '''Suppress the expected warning when initialize_ok=False.'''
    def __enter__(self):
        self._cm = unittest.TestCase().assertLogs(
            'QVideo.lib.QVideoReader', level='WARNING')
        self._cm.__enter__()
        return self

    def __exit__(self, *args):
        self._cm.__exit__(*args)


class TestInit(unittest.TestCase):

    def test_filename_stored(self):
        reader = make_reader('my_video.avi')
        self.assertEqual(reader.filename, 'my_video.avi')

    def test_has_mutex(self):
        reader = make_reader()
        self.assertIsInstance(reader.mutex, QtCore.QMutex)

    def test_has_waitcondition(self):
        reader = make_reader()
        self.assertIsInstance(reader.waitcondition, QtCore.QWaitCondition)

    def test_initially_not_paused(self):
        reader = make_reader()
        self.assertFalse(reader.isPaused())

    def test_auto_opens_on_init(self):
        reader = make_reader()
        self.assertTrue(reader.isOpen())


class TestOpen(unittest.TestCase):

    def test_open_returns_self(self):
        reader = make_reader()
        reader.close()
        self.assertIs(reader.open(), reader)

    def test_open_sets_isopen(self):
        reader = make_reader()
        reader.close()
        reader.open()
        self.assertTrue(reader.isOpen())

    def test_open_calls_initialize(self):
        reader = make_reader()
        self.assertEqual(reader._initialize_called, 1)

    def test_open_is_idempotent(self):
        reader = make_reader()
        reader.open()
        self.assertEqual(reader._initialize_called, 1)

    def test_open_emits_shape_changed(self):
        reader = make_reader()
        reader.close()
        spy = QtTest.QSignalSpy(reader.shapeChanged)
        reader.open()
        self.assertEqual(len(spy), 1)

    def test_open_warns_on_failure(self):
        with self.assertLogs('QVideo.lib.QVideoReader', level='WARNING') as cm:
            reader = _FakeVideoReader(initialize_ok=False)
        self.assertTrue(any('initialization failed' in line for line in cm.output))
        self.assertFalse(reader.isOpen())

    def test_open_coerces_initialize_return_to_bool(self):
        reader = make_reader()
        self.assertIsInstance(reader._isopen, bool)

    def test_open_does_not_emit_shape_changed_on_failure(self):
        reader = _FakeVideoReader(initialize_ok=False)
        spy = QtTest.QSignalSpy(reader.shapeChanged)
        with self.assertLogs('QVideo.lib.QVideoReader', level='WARNING'):
            reader.open()
        self.assertEqual(len(spy), 0)


class TestClose(unittest.TestCase):

    def test_close_clears_isopen(self):
        reader = make_reader()
        reader.close()
        self.assertFalse(reader.isOpen())

    def test_close_calls_deinitialize(self):
        reader = make_reader()
        reader.close()
        self.assertEqual(reader._deinitialize_called, 1)

    def test_close_is_idempotent(self):
        reader = make_reader()
        reader.close()
        reader.close()
        self.assertEqual(reader._deinitialize_called, 1)

    def test_close_when_never_opened(self):
        with self.assertLogs('QVideo.lib.QVideoReader', level='WARNING'):
            reader = _FakeVideoReader(initialize_ok=False)
        try:
            reader.close()
        except Exception as e:
            self.fail(f'close() on unopened reader raised {e}')


class TestContextManager(unittest.TestCase):

    def test_enter_opens(self):
        reader = make_reader()
        reader.close()
        with reader:
            self.assertTrue(reader.isOpen())

    def test_exit_closes(self):
        reader = make_reader()
        with reader:
            pass
        self.assertFalse(reader.isOpen())

    def test_can_reopen_after_context(self):
        reader = make_reader()
        with reader:
            pass
        with reader:
            self.assertTrue(reader.isOpen())


class TestProperties(unittest.TestCase):

    def test_shape_returns_qsize(self):
        reader = make_reader()
        self.assertIsInstance(reader.shape, QtCore.QSize)

    def test_shape_matches_width_height(self):
        reader = make_reader()
        self.assertEqual(reader.shape, QtCore.QSize(640, 480))

    def test_delay_is_int(self):
        reader = make_reader()
        self.assertIsInstance(reader.delay, int)

    def test_delay_derived_from_fps(self):
        reader = make_reader()
        self.assertEqual(reader.delay, int(1000. / reader.fps))

    def test_fps(self):
        reader = make_reader()
        self.assertAlmostEqual(reader.fps, 30.)

    def test_width(self):
        reader = make_reader()
        self.assertEqual(reader.width, 640)

    def test_height(self):
        reader = make_reader()
        self.assertEqual(reader.height, 480)

    def test_length(self):
        reader = make_reader()
        self.assertEqual(reader.length, 100)

    def test_framenumber_increments_on_read(self):
        reader = make_reader()
        reader.read()
        self.assertEqual(reader.framenumber, 1)


class TestPauseResume(unittest.TestCase):

    def test_pause_sets_paused(self):
        reader = make_reader()
        reader.pause()
        self.assertTrue(reader.isPaused())

    def test_ispaused_reflects_state(self):
        reader = make_reader()
        self.assertFalse(reader.isPaused())
        reader.pause()
        self.assertTrue(reader.isPaused())

    def test_resume_clears_paused(self):
        reader = make_reader()
        reader.pause()
        reader.resume()
        self.assertFalse(reader.isPaused())

    def test_resume_wakes_waitcondition(self):
        reader = make_reader()
        with patch.object(reader.waitcondition, 'wakeAll') as mock_wake:
            reader.resume()
        mock_wake.assert_called_once()


class TestSaferead(unittest.TestCase):

    def test_saferead_calls_read(self):
        reader = make_reader()
        with patch.object(reader.waitcondition, 'wait'):
            with patch.object(reader, 'read', wraps=reader.read) as mock_read:
                reader.saferead()
        mock_read.assert_called_once()

    def test_saferead_waits_with_delay_when_not_paused(self):
        reader = make_reader()
        with patch.object(reader.waitcondition, 'wait') as mock_wait:
            reader.saferead()
        mock_wait.assert_called_once_with(reader.mutex, reader.delay)

    def test_saferead_waits_indefinitely_when_paused(self):
        reader = make_reader()
        reader._paused = True
        with patch.object(reader.waitcondition, 'wait') as mock_wait:
            reader.saferead()
        mock_wait.assert_called_once_with(reader.mutex)

    def test_saferead_returns_frame(self):
        reader = make_reader()
        with patch.object(reader.waitcondition, 'wait'):
            ok, frame = reader.saferead()
        self.assertTrue(ok)
        self.assertIsInstance(frame, np.ndarray)


class TestSeekRewind(unittest.TestCase):

    def test_seek_sets_framenumber(self):
        reader = make_reader()
        reader.seek(42)
        self.assertEqual(reader.framenumber, 42)

    def test_rewind_seeks_to_zero(self):
        reader = make_reader()
        reader.seek(10)
        reader.rewind()
        self.assertEqual(reader.framenumber, 0)


if __name__ == '__main__':
    unittest.main()
