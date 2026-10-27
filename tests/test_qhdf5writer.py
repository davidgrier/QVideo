'''Unit tests for QHDF5Writer.'''
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
from unittest.mock import patch, MagicMock
from qtpy import QtWidgets
from QVideo.dvr.QHDF5Writer import QHDF5Writer
from QVideo.dvr.QHDF5Reader import QHDF5Reader
from QVideo.lib.videotypes import FrameInfo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

writer_module = sys.modules['QVideo.dvr.QHDF5Writer']  # not the class

_FRAME = np.zeros((480, 640), dtype=np.uint8)


def make_mock_h5file():
    '''Return (mock_file, mock_images_group) with h5py-like behavior.'''
    mock_group = MagicMock()
    is_open = [True]
    mock_file = MagicMock()
    mock_file.__bool__ = MagicMock(side_effect=lambda: is_open[0])
    mock_file.create_group.return_value = mock_group

    def _close():
        is_open[0] = False

    mock_file.close.side_effect = _close
    return mock_file, mock_group


def make_writer(**kwargs):
    return QHDF5Writer('test.h5', fps=30, **kwargs)


class TestQHDF5WriterInit(unittest.TestCase):

    def test_not_open_before_first_frame(self):
        writer = make_writer()
        self.assertFalse(writer.isOpen())

    def test_file_is_none_initially(self):
        writer = make_writer()
        self.assertIsNone(writer._file)


class TestQHDF5WriterOpen(unittest.TestCase):

    def test_open_returns_true(self):
        writer = make_writer()
        mock_file, _ = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            result = writer.open(_FRAME)
        self.assertTrue(result)

    def test_open_returns_false_on_oserror(self):
        writer = make_writer()
        with patch('h5py.File', side_effect=OSError):
            with self.assertLogs('QVideo.dvr.QHDF5Writer', level='WARNING'):
                result = writer.open(_FRAME)
        self.assertFalse(result)

    def test_open_creates_images_group(self):
        writer = make_writer()
        mock_file, _ = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        mock_file.create_group.assert_called_once_with('images')

    def test_open_does_not_yet_set_timestamp_attribute(self):
        writer = make_writer()
        mock_file, _ = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        mock_file.attrs.__setitem__.assert_not_called()

    def test_isopen_true_after_open(self):
        writer = make_writer()
        mock_file, _ = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        self.assertTrue(writer.isOpen())

    def test_isopen_false_after_failed_open(self):
        writer = make_writer()
        with patch('h5py.File', side_effect=OSError):
            with self.assertLogs('QVideo.dvr.QHDF5Writer', level='WARNING'):
                writer.open(_FRAME)
        self.assertFalse(writer.isOpen())


class TestQHDF5WriterInternalWrite(unittest.TestCase):

    def _open_writer(self):
        writer = make_writer()
        mock_file, mock_group = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        return writer, mock_group

    def test_write_creates_dataset(self):
        writer, mock_group = self._open_writer()
        writer._write(_FRAME)
        mock_group.create_dataset.assert_called_once()

    def test_write_stores_frame_data(self):
        writer, mock_group = self._open_writer()
        writer._write(_FRAME)
        _, kwargs = mock_group.create_dataset.call_args
        np.testing.assert_array_equal(kwargs['data'], _FRAME)

    def test_write_dataset_key_is_elapsed_time(self):
        writer, mock_group = self._open_writer()
        writer._write(_FRAME)
        key = mock_group.create_dataset.call_args[0][0]
        self.assertIsInstance(float(key), float)

    def test_write_dataset_key_has_nanosecond_precision(self):
        writer, mock_group = self._open_writer()
        writer._write(_FRAME)
        key = mock_group.create_dataset.call_args[0][0]
        # Key must be fixed-point with exactly 9 decimal places
        self.assertRegex(key, r'^\d+\.\d{9}$')

    def test_successive_writes_use_different_keys(self):
        writer, mock_group = self._open_writer()
        writer._write(_FRAME)
        writer._write(_FRAME)
        keys = [call[0][0] for call in mock_group.create_dataset.call_args_list]
        self.assertEqual(len(set(keys)), 2)


class TestQHDF5WriterCompression(unittest.TestCase):

    def roundtrip(self, frames, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'test.h5')
            writer = QHDF5Writer(path, fps=30, **kwargs)
            for i, frame in enumerate(frames):
                writer.write(frame, FrameInfo(i, i / 30.))
            writer.close()
            reader = QHDF5Reader(path)
            back = [reader.read()[1] for _ in frames]
            reader.close()  # Windows cannot delete a file that is open
            return back, Path(path).stat().st_size

    def frames(self, dtype):
        rng = np.random.default_rng(0)
        high = np.iinfo(dtype).max + 1
        ramp = np.linspace(0, high - 1, 64 * 48).reshape(48, 64)
        return [(ramp + rng.integers(0, 4, ramp.shape)).clip(
            0, high - 1).astype(dtype) for _ in range(4)]

    def test_every_filter_returns_every_pixel(self):
        filters = [None, 'lzf', 'gzip']
        if writer_module.hdf5plugin is not None:
            filters += ['zstd', 'lz4', 'blosc2']
        for dtype in (np.uint8, np.uint16):
            frames = self.frames(dtype)
            for name in filters:
                with self.subTest(dtype=dtype.__name__, compression=name):
                    back, _ = self.roundtrip(frames, compression=name)
                    for sent, got in zip(frames, back):
                        np.testing.assert_array_equal(sent, got)

    def test_compression_makes_the_file_smaller(self):
        frames = [np.zeros((256, 256), np.uint8) for _ in range(4)]
        _, raw = self.roundtrip(frames, compression=None)
        _, packed = self.roundtrip(frames, compression='lzf')
        self.assertLess(packed, raw)

    def test_zstandard_is_the_default(self):
        with patch.object(writer_module, '_filter') as chosen:
            make_writer()
        chosen.assert_called_once_with('zstd')

    def test_no_compression_gives_no_filter(self):
        self.assertEqual(writer_module._filter(None), {})

    def test_builtin_filters_need_no_plugin(self):
        with patch.object(writer_module, 'hdf5plugin', None):
            self.assertEqual(writer_module._filter('lzf'),
                             {'compression': 'lzf'})
            self.assertEqual(writer_module._filter('gzip')['compression'],
                             'gzip')

    def test_without_the_plugin_frames_are_stored_uncompressed(self):
        with patch.object(writer_module, 'hdf5plugin', None):
            with self.assertLogs('QVideo.dvr.QHDF5Writer', 'INFO'):
                self.assertEqual(writer_module._filter('zstd'), {})

    def test_a_compressed_dataset_is_one_chunk(self):
        writer = make_writer(compression='lzf')
        mock_file, mock_group = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        writer._write(_FRAME)
        kwargs = mock_group.create_dataset.call_args.kwargs
        self.assertEqual(kwargs['chunks'], _FRAME.shape)
        self.assertEqual(kwargs['compression'], 'lzf')

    def test_an_uncompressed_dataset_is_contiguous(self):
        writer = make_writer(compression=None)
        mock_file, mock_group = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        writer._write(_FRAME)
        self.assertIsNone(mock_group.create_dataset.call_args.kwargs['chunks'])


class TestQHDF5WriterCaptureTimes(unittest.TestCase):
    '''Datasets are keyed by capture time, not by write time.'''

    def _open_writer(self):
        writer = make_writer()
        mock_file, mock_group = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        return writer, mock_file, mock_group

    def test_keys_follow_capture_timestamps(self):
        writer, _, group = self._open_writer()
        writer._write(_FRAME, FrameInfo(0, 10.00))
        writer._write(_FRAME, FrameInfo(1, 10.25))
        keys = [c[0][0] for c in group.create_dataset.call_args_list]
        self.assertEqual(keys, ['0.000000000', '0.250000000'])

    def test_timestamp_attribute_is_first_frame_wallclock(self):
        writer, mock_file, _ = self._open_writer()
        info = FrameInfo(0, 10.0)
        writer._write(_FRAME, info)
        key, value = mock_file.attrs.__setitem__.call_args[0]
        self.assertEqual(key, 'Timestamp')
        self.assertAlmostEqual(value, info.wallclock, delta=0.05)

    def test_timestamp_attribute_set_only_once(self):
        writer, mock_file, _ = self._open_writer()
        writer._write(_FRAME, FrameInfo(0, 10.0))
        writer._write(_FRAME, FrameInfo(1, 10.1))
        mock_file.attrs.__setitem__.assert_called_once()

    def test_close_resets_start_for_next_recording(self):
        writer, _, _ = self._open_writer()
        writer._write(_FRAME, FrameInfo(0, 10.0))
        writer.close()
        self.assertIsNone(writer._t0)


class TestQHDF5WriterClose(unittest.TestCase):

    def test_close_closes_file(self):
        writer = make_writer()
        mock_file, _ = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        writer.close()
        mock_file.close.assert_called_once()

    def test_close_sets_file_to_none(self):
        writer = make_writer()
        mock_file, _ = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        writer.close()
        self.assertIsNone(writer._file)

    def test_isopen_false_after_close(self):
        writer = make_writer()
        mock_file, _ = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        writer.close()
        self.assertFalse(writer.isOpen())

    def test_close_when_not_open_is_safe(self):
        writer = make_writer()
        writer.close()
        self.assertIsNone(writer._file)


if __name__ == '__main__':
    unittest.main()
