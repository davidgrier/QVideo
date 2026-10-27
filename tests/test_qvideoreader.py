'''Unit tests for QVideoReader.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.tests.signals import record
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
        spy = record(reader.shapeChanged)
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
        spy = record(reader.shapeChanged)
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

    def test_actual_fps_is_the_rate_of_the_file(self):
        reader = make_reader()
        self.assertEqual(reader.actualFps, reader.fps)

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


class TestSaferead(unittest.TestCase):

    def test_saferead_calls_read(self):
        reader = make_reader()
        with patch.object(QtCore.QThread, 'msleep'):
            with patch.object(reader, 'read', wraps=reader.read) as mock_read:
                reader.saferead()
        mock_read.assert_called_once()

    def test_saferead_sleeps_for_delay(self):
        reader = make_reader()
        with patch.object(QtCore.QThread, 'msleep') as mock_sleep:
            reader.saferead()
        mock_sleep.assert_called_once_with(reader.delay)

    def test_saferead_returns_frame(self):
        reader = make_reader()
        with patch.object(QtCore.QThread, 'msleep'):
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


class _Counting(_FakeVideoReader):
    '''A reader of ten frames, each filled with its own index.'''

    def __init__(self, length=10):
        super().__init__()
        self._length = length

    def read(self):
        if self._framenumber >= self._length:
            return False, None
        frame = np.full((2, 2), self._framenumber, np.uint8)
        self._framenumber += 1
        return True, frame


class _Lying(_Counting):
    """A reader that claims ten frames but has only seven."""

    def read(self):
        if self._framenumber >= 7:
            return False, None
        return super().read()


def values(frames):
    return [int(f[0, 0]) for f in frames]


class TestSequence(unittest.TestCase):
    '''A reader can be used like a sequence of frames.'''

    def setUp(self):
        self.video = _Counting()

    def test_len_is_the_number_of_frames(self):
        self.assertEqual(len(self.video), 10)

    def test_len_of_a_closed_reader_is_zero(self):
        self.video.close()
        self.assertEqual(len(self.video), 0)

    def test_a_reader_is_true_even_without_frames(self):
        self.assertTrue(_Counting(length=0))

    def test_an_index_gives_that_frame(self):
        self.assertEqual(values([self.video[0], self.video[7]]), [0, 7])

    def test_a_negative_index_counts_from_the_end(self):
        self.assertEqual(int(self.video[-1][0, 0]), 9)
        self.assertEqual(int(self.video[-10][0, 0]), 0)

    def test_an_index_outside_the_video_is_an_error(self):
        for index in (10, -11, 100):
            with self.subTest(index):
                with self.assertRaises(IndexError):
                    self.video[index]

    def test_a_frame_that_cannot_be_read_is_an_error(self):
        self.video.read = lambda: (False, None)
        with self.assertRaises(IndexError):
            self.video[3]

    def test_a_slice_gives_a_list_of_frames(self):
        self.assertEqual(values(self.video[2:6]), [2, 3, 4, 5])

    def test_a_slice_with_a_step(self):
        self.assertEqual(values(self.video[::3]), [0, 3, 6, 9])
        self.assertEqual(values(self.video[8:1:-3]), [8, 5, 2])

    def test_a_slice_outside_the_video_is_shortened(self):
        self.assertEqual(values(self.video[7:100]), [7, 8, 9])
        self.assertEqual(self.video[20:30], [])

    def test_a_slice_ends_where_a_frame_cannot_be_read(self):
        video = _Lying()
        self.assertEqual(values(video[5:10]), [5, 6])
        self.assertEqual(values(video[0:10:2]), [0, 2, 4, 6])
        self.assertEqual(values(video[:]), list(range(7)))

    def test_a_slice_never_contains_a_missing_frame(self):
        self.assertTrue(all(f is not None for f in _Lying()[3:10]))

    def test_the_whole_video_is_a_slice(self):
        self.assertEqual(values(self.video[:]), list(range(10)))

    def test_iteration_starts_from_the_first_frame(self):
        self.video.seek(6)
        self.assertEqual(values(self.video), list(range(10)))

    def test_it_can_be_iterated_twice(self):
        self.assertEqual(values(self.video), values(self.video))

    def test_it_works_as_a_context_manager(self):
        with _Counting() as video:
            self.assertEqual(len(video), 10)
        self.assertEqual(len(video), 0)


if __name__ == '__main__':
    unittest.main()
