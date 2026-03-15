'''Unit tests for QHDF5Writer.'''
import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from pyqtgraph.Qt import QtWidgets
from QVideo.dvr.QHDF5Writer import QHDF5Writer


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640), dtype=np.uint8)


def make_mock_h5file():
    '''Return (mock_file, mock_images_group) with h5py-like behaviour.'''
    mock_group = MagicMock()
    is_open = [True]
    mock_file = MagicMock()
    mock_file.__bool__ = MagicMock(side_effect=lambda: is_open[0])
    mock_file.create_group.return_value = mock_group

    def _close():
        is_open[0] = False

    mock_file.close.side_effect = _close
    return mock_file, mock_group


def make_writer():
    return QHDF5Writer('test.h5', fps=30)


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

    def test_open_writes_timestamp_attribute(self):
        writer = make_writer()
        mock_file, _ = make_mock_h5file()
        with patch('h5py.File', return_value=mock_file):
            writer.open(_FRAME)
        mock_file.attrs.update.assert_called_once()
        attrs = mock_file.attrs.update.call_args[0][0]
        self.assertIn('Timestamp', attrs)

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
