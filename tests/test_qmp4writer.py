'''Unit tests for QMP4Writer.'''
import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from pyqtgraph.Qt import QtWidgets
import cv2
from QVideo.dvr.QMP4Writer import QMP4Writer
from QVideo.dvr.QOpenCVWriter import QOpenCVWriter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME_COLOR = np.zeros((480, 640, 3), dtype=np.uint8)
_FRAME_GRAY = np.zeros((480, 640), dtype=np.uint8)


def make_mock_vw(opened=True):
    vw = MagicMock()
    vw.isOpened.return_value = opened
    return vw


def make_writer(**kwargs):
    return QMP4Writer('test.mp4', fps=30, **kwargs)


class TestQMP4WriterClass(unittest.TestCase):

    def test_is_subclass_of_qopencvwriter(self):
        self.assertTrue(issubclass(QMP4Writer, QOpenCVWriter))

    def test_avc1_is_first_preference(self):
        self.assertEqual(QMP4Writer.CODECS[0], 'avc1')

    def test_mp4v_is_fallback(self):
        self.assertIn('mp4v', QMP4Writer.CODECS)


class TestQMP4WriterInit(unittest.TestCase):

    def test_not_open_before_first_frame(self):
        writer = make_writer()
        self.assertFalse(writer.isOpen())

    def test_writer_is_none_initially(self):
        writer = make_writer()
        self.assertIsNone(writer._writer)

    def test_default_codec_preference_order(self):
        writer = make_writer()
        self.assertEqual(writer._codecs, QMP4Writer.CODECS)

    def test_custom_codec_bypasses_probing(self):
        writer = make_writer(codec='XVID')
        self.assertEqual(writer._codecs, ('XVID',))


class TestQMP4WriterOpen(unittest.TestCase):

    def test_open_tries_avc1_first(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)) as mock_cls:
            writer.open(_FRAME_COLOR)
        first_fourcc = mock_cls.call_args_list[0][0][1]
        self.assertEqual(first_fourcc, cv2.VideoWriter_fourcc(*'avc1'))

    def test_open_returns_true_when_first_codec_works(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)):
            result = writer.open(_FRAME_COLOR)
        self.assertTrue(result)

    def test_open_falls_back_to_mp4v_if_avc1_unavailable(self):
        writer = make_writer()
        with patch('cv2.VideoWriter',
                   side_effect=[make_mock_vw(False), make_mock_vw(True)]):
            result = writer.open(_FRAME_COLOR)
        self.assertTrue(result)

    def test_open_returns_false_when_all_codecs_fail(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(False)):
            with self.assertLogs('QVideo.dvr.QOpenCVWriter', level='WARNING'):
                result = writer.open(_FRAME_COLOR)
        self.assertFalse(result)

    def test_open_passes_correct_dimensions(self):
        writer = make_writer()
        with patch('cv2.VideoWriter') as mock_cls:
            mock_cls.return_value = make_mock_vw(True)
            writer.open(_FRAME_COLOR)
        w, h = mock_cls.call_args[0][3]
        self.assertEqual(w, 640)
        self.assertEqual(h, 480)


class TestQMP4WriterClose(unittest.TestCase):

    def test_close_releases_video_writer(self):
        writer = make_writer()
        mock_vw = make_mock_vw(True)
        with patch('cv2.VideoWriter', return_value=mock_vw):
            writer.open(_FRAME_COLOR)
        writer.close()
        mock_vw.release.assert_called_once()

    def test_isopen_false_after_close(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)):
            writer.open(_FRAME_COLOR)
        writer.close()
        self.assertFalse(writer.isOpen())

    def test_close_when_not_open_is_safe(self):
        writer = make_writer()
        writer.close()
        self.assertIsNone(writer._writer)


if __name__ == '__main__':
    unittest.main()
