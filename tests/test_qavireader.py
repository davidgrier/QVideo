'''Unit tests for QAVIReader and QAVISource.'''
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from pyqtgraph.Qt import QtWidgets
from QVideo.dvr.QAVIReader import QAVIReader, QAVISource


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME_BGR = np.zeros((480, 640, 3), dtype=np.uint8)
_FRAME_GRAY = np.zeros((480, 640), dtype=np.uint8)


def make_mock_capture(width=640, height=480, fps=30., length=100,
                      read_ok=True, frame=None, opened=True):
    '''Return a MagicMock standing in for cv2.VideoCapture.'''
    if frame is None:
        frame = _FRAME_BGR.copy()
    cap = MagicMock()
    cap.isOpened.return_value = opened
    cap.read.return_value = (read_ok, frame)

    def _get(prop):
        return {
            QAVIReader.WIDTH: width,
            QAVIReader.HEIGHT: height,
            QAVIReader.FPS: fps,
            QAVIReader.LENGTH: length,
            QAVIReader.FRAMENUMBER: 0,
        }.get(prop, 0.)

    cap.get.side_effect = _get
    return cap


def make_reader(**kwargs):
    '''Return a QAVIReader with a mocked VideoCapture.'''
    cap = make_mock_capture(**kwargs)
    with patch('cv2.VideoCapture', return_value=cap):
        reader = QAVIReader('test.avi')
    return reader


class TestQAVIReaderInit(unittest.TestCase):

    def test_opens_on_init(self):
        reader = make_reader()
        self.assertTrue(reader.isOpen())

    def test_fails_if_capture_not_opened(self):
        with self.assertLogs('QVideo.lib.QVideoReader', level='WARNING'):
            reader = make_reader(opened=False)
        self.assertFalse(reader.isOpen())

    def test_fps(self):
        reader = make_reader(fps=25.)
        self.assertAlmostEqual(reader.fps, 25.)

    def test_length(self):
        reader = make_reader(length=200)
        self.assertEqual(reader.length, 200)

    def test_width(self):
        reader = make_reader(width=320)
        self.assertEqual(reader.width, 320)

    def test_height(self):
        reader = make_reader(height=240)
        self.assertEqual(reader.height, 240)

    def test_framenumber_starts_at_zero(self):
        reader = make_reader()
        self.assertEqual(reader.framenumber, 0)


class TestQAVIReaderRead(unittest.TestCase):

    def test_read_returns_true_on_success(self):
        reader = make_reader()
        ok, _ = reader.read()
        self.assertTrue(ok)

    def test_read_returns_ndarray(self):
        reader = make_reader()
        _, frame = reader.read()
        self.assertIsInstance(frame, np.ndarray)

    def test_read_color_frame_converted_to_rgb(self):
        reader = make_reader(frame=_FRAME_BGR.copy())
        with patch('cv2.cvtColor', return_value=_FRAME_BGR) as mock_cvt:
            reader.read()
        mock_cvt.assert_called_once()
        _, code = mock_cvt.call_args[0]
        self.assertEqual(code, QAVIReader._COLOR_BGR2RGB)

    def test_read_grayscale_frame_not_converted(self):
        reader = make_reader(frame=_FRAME_GRAY.copy())
        with patch('cv2.cvtColor') as mock_cvt:
            reader.read()
        mock_cvt.assert_not_called()

    def test_read_failure_returns_false_none(self):
        reader = make_reader(read_ok=False)
        ok, frame = reader.read()
        self.assertFalse(ok)
        self.assertIsNone(frame)

    def test_read_when_closed_returns_false_none(self):
        with self.assertLogs('QVideo.lib.QVideoReader', level='WARNING'):
            reader = make_reader(opened=False)
        ok, frame = reader.read()
        self.assertFalse(ok)
        self.assertIsNone(frame)

    def test_read_increments_framenumber(self):
        reader = make_reader()
        reader.read()
        self.assertEqual(reader.framenumber, 1)

    def test_failed_read_does_not_increment_framenumber(self):
        reader = make_reader(read_ok=False)
        reader.read()
        self.assertEqual(reader.framenumber, 0)


class TestQAVIReaderSeek(unittest.TestCase):

    def test_seek_calls_capture_set(self):
        reader = make_reader()
        reader.seek(42)
        reader.reader.set.assert_called_with(QAVIReader.FRAMENUMBER, 42)

    def test_seek_updates_framenumber(self):
        reader = make_reader()
        reader.seek(42)
        self.assertEqual(reader.framenumber, 42)

    def test_rewind_seeks_to_zero(self):
        reader = make_reader()
        reader.rewind()
        reader.reader.set.assert_called_with(QAVIReader.FRAMENUMBER, 0)

    def test_rewind_resets_framenumber(self):
        reader = make_reader()
        reader.seek(10)
        reader.rewind()
        self.assertEqual(reader.framenumber, 0)


class TestQAVIReaderClose(unittest.TestCase):

    def test_close_releases_capture(self):
        reader = make_reader()
        cap = reader.reader
        reader.close()
        cap.release.assert_called_once()

    def test_isopen_false_after_close(self):
        reader = make_reader()
        reader.close()
        self.assertFalse(reader.isOpen())

    def test_close_sets_reader_to_none(self):
        reader = make_reader()
        reader.close()
        self.assertIsNone(reader.reader)


class TestQAVISource(unittest.TestCase):

    def test_accepts_string_filename(self):
        cap = make_mock_capture()
        with patch('cv2.VideoCapture', return_value=cap):
            src = QAVISource('test.avi')
        self.assertIsInstance(src.source, QAVIReader)

    def test_accepts_path_filename(self):
        cap = make_mock_capture()
        with patch('cv2.VideoCapture', return_value=cap):
            src = QAVISource(Path('test.avi'))
        self.assertIsInstance(src.source, QAVIReader)

    def test_accepts_reader_instance(self):
        reader = make_reader()
        src = QAVISource(reader)
        self.assertIs(src.source, reader)


if __name__ == '__main__':
    unittest.main()
