'''Unit tests for QHDF5Reader and QHDF5Source.'''
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from pyqtgraph.Qt import QtWidgets
from QVideo.dvr.QHDF5Reader import QHDF5Reader, QHDF5Source


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# Non-square frame so width/height are distinguishable
_FRAME = np.zeros((480, 640), dtype=np.uint8)


def make_mock_file(frames=None, fps=30.):
    '''Return a mock h5py.File containing the given frames.'''
    if frames is None:
        frames = [_FRAME.copy() for _ in range(3)]
    keys = [f'{i / fps:.9f}' for i in range(len(frames))]

    datasets = {}
    for key, frame in zip(keys, frames):
        ds = MagicMock()
        ds.__getitem__ = MagicMock(return_value=frame)
        datasets[key] = ds

    images = MagicMock()
    images.keys.return_value = keys
    images.__getitem__ = MagicMock(side_effect=lambda k: datasets[k])

    file = MagicMock()
    file.__getitem__ = MagicMock(side_effect=lambda k: images if k == 'images' else None)
    return file, keys, frames


def make_reader(frames=None, fps=30.):
    '''Return a QHDF5Reader backed by a mock h5py.File.'''
    mock_file, keys, frames = make_mock_file(frames, fps=fps)
    with patch('h5py.File', return_value=mock_file):
        reader = QHDF5Reader('test.h5')
    return reader


class TestQHDF5ReaderInit(unittest.TestCase):

    def test_opens_on_init(self):
        reader = make_reader()
        self.assertTrue(reader.isOpen())

    def test_init_fails_on_oserror(self):
        with patch('h5py.File', side_effect=OSError):
            with self.assertLogs('QVideo.lib.QVideoReader', level='WARNING'):
                reader = QHDF5Reader('missing.h5')
        self.assertFalse(reader.isOpen())

    def test_init_fails_on_empty_images_group(self):
        mock_file = MagicMock()
        images = MagicMock()
        images.keys.return_value = []
        mock_file.__getitem__ = MagicMock(
            side_effect=lambda k: images if k == 'images' else None)
        with patch('h5py.File', return_value=mock_file):
            with self.assertLogs('QVideo.lib.QVideoReader', level='WARNING'):
                reader = QHDF5Reader('test.h5')
        self.assertFalse(reader.isOpen())

    def test_init_fails_on_missing_images_group(self):
        mock_file = MagicMock()
        mock_file.__getitem__ = MagicMock(side_effect=KeyError('images'))
        with patch('h5py.File', return_value=mock_file):
            with self.assertLogs('QVideo.lib.QVideoReader', level='WARNING'):
                reader = QHDF5Reader('test.h5')
        self.assertFalse(reader.isOpen())

    def test_framenumber_starts_at_zero(self):
        reader = make_reader()
        self.assertEqual(reader.framenumber, 0)

    def test_length(self):
        reader = make_reader([_FRAME.copy() for _ in range(5)])
        self.assertEqual(reader.length, 5)

    def test_fps_computed_from_timestamps(self):
        reader = make_reader(fps=30.)
        self.assertAlmostEqual(reader.fps, 30., places=6)

    def test_fps_computed_at_non_standard_rate(self):
        reader = make_reader(fps=60.)
        self.assertAlmostEqual(reader.fps, 60., places=3)

    def test_fps_single_frame_returns_default(self):
        reader = make_reader([_FRAME.copy()])
        self.assertAlmostEqual(reader.fps, 30.)

    def test_width_from_frame_shape(self):
        reader = make_reader()
        self.assertEqual(reader.width, _FRAME.shape[1])  # shape[1] is width

    def test_height_from_frame_shape(self):
        reader = make_reader()
        self.assertEqual(reader.height, _FRAME.shape[0])  # shape[0] is height


    def test_keys_sorted_by_timestamp(self):
        '''Keys must be in temporal order regardless of HDF5 insertion order.'''
        frames = [_FRAME.copy() for _ in range(3)]
        # Deliberately reverse the key order to simulate a non-track_order file
        keys = ['0.066666667', '0.000000000', '0.033333333']
        datasets = {k: MagicMock(__getitem__=MagicMock(return_value=f))
                    for k, f in zip(keys, frames)}
        images = MagicMock()
        images.keys.return_value = keys
        images.__getitem__ = MagicMock(side_effect=lambda k: datasets[k])
        mock_file = MagicMock()
        mock_file.__getitem__ = MagicMock(
            side_effect=lambda k: images if k == 'images' else None)
        with patch('h5py.File', return_value=mock_file):
            reader = QHDF5Reader('test.h5')
        self.assertEqual(reader.keys,
                         ['0.000000000', '0.033333333', '0.066666667'])


class TestQHDF5ReaderRead(unittest.TestCase):

    def test_read_returns_true_on_success(self):
        reader = make_reader()
        ok, frame = reader.read()
        self.assertTrue(ok)

    def test_read_returns_array(self):
        reader = make_reader()
        ok, frame = reader.read()
        self.assertIsInstance(frame, np.ndarray)

    def test_read_does_not_cache_frame_as_attribute(self):
        reader = make_reader()
        reader.read()
        self.assertFalse(hasattr(reader, 'frame'))

    def test_read_increments_framenumber(self):
        reader = make_reader()
        reader.read()
        self.assertEqual(reader.framenumber, 1)

    def test_read_past_end_returns_false_none(self):
        reader = make_reader([_FRAME.copy()])
        reader.read()
        ok, frame = reader.read()
        self.assertFalse(ok)
        self.assertIsNone(frame)

    def test_read_all_frames_in_sequence(self):
        n = 4
        reader = make_reader([_FRAME.copy() for _ in range(n)])
        for _ in range(n):
            ok, _ = reader.read()
            self.assertTrue(ok)
        self.assertEqual(reader.framenumber, n)


class TestQHDF5ReaderSeek(unittest.TestCase):

    def test_seek_sets_framenumber(self):
        reader = make_reader([_FRAME.copy() for _ in range(5)])
        reader.seek(3)
        self.assertEqual(reader.framenumber, 3)

    def test_seek_then_read_advances_from_new_position(self):
        reader = make_reader([_FRAME.copy() for _ in range(5)])
        reader.seek(2)
        reader.read()
        self.assertEqual(reader.framenumber, 3)

    def test_rewind_resets_to_zero(self):
        reader = make_reader([_FRAME.copy() for _ in range(5)])
        reader.seek(3)
        reader.rewind()
        self.assertEqual(reader.framenumber, 0)


class TestQHDF5ReaderClose(unittest.TestCase):

    def test_close_calls_file_close(self):
        mock_file, _, _ = make_mock_file()
        with patch('h5py.File', return_value=mock_file):
            reader = QHDF5Reader('test.h5')
        reader.close()
        mock_file.close.assert_called_once()

    def test_isopen_false_after_close(self):
        reader = make_reader()
        reader.close()
        self.assertFalse(reader.isOpen())


class TestQHDF5Source(unittest.TestCase):

    def test_accepts_string_filename(self):
        mock_file, _, _ = make_mock_file()
        with patch('h5py.File', return_value=mock_file):
            src = QHDF5Source('test.h5')
        self.assertIsInstance(src.source, QHDF5Reader)

    def test_accepts_path_filename(self):
        mock_file, _, _ = make_mock_file()
        with patch('h5py.File', return_value=mock_file):
            src = QHDF5Source(Path('test.h5'))
        self.assertIsInstance(src.source, QHDF5Reader)

    def test_accepts_reader_instance(self):
        reader = make_reader()
        src = QHDF5Source(reader)
        self.assertIs(src.source, reader)


if __name__ == '__main__':
    unittest.main()
