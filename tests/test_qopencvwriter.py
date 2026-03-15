'''Unit tests for QOpenCVWriter.'''
import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from pyqtgraph.Qt import QtWidgets
import cv2
from QVideo.dvr.QOpenCVWriter import QOpenCVWriter
from QVideo.lib import QVideoWriter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME_COLOR = np.zeros((480, 640, 3), dtype=np.uint8)
_FRAME_GRAY = np.zeros((480, 640), dtype=np.uint8)


def make_mock_vw(opened=True):
    vw = MagicMock()
    vw.isOpened.return_value = opened
    return vw


class _ConcreteWriter(QOpenCVWriter):
    '''Minimal concrete subclass for testing.'''
    CODECS = ('FAKE',)


def make_writer(**kwargs):
    return _ConcreteWriter('test.avi', fps=30, **kwargs)


class TestQOpenCVWriterClass(unittest.TestCase):

    def test_is_subclass_of_qvideowriter(self):
        self.assertTrue(issubclass(QOpenCVWriter, QVideoWriter))

    def test_default_codecs_is_empty(self):
        self.assertEqual(QOpenCVWriter.CODECS, ())


class TestQOpenCVWriterInit(unittest.TestCase):

    def test_not_open_before_first_frame(self):
        writer = make_writer()
        self.assertFalse(writer.isOpen())

    def test_writer_is_none_initially(self):
        writer = make_writer()
        self.assertIsNone(writer._writer)

    def test_shape_is_none_initially(self):
        writer = make_writer()
        self.assertIsNone(writer._shape)

    def test_custom_codec_overrides_class_codecs(self):
        writer = make_writer(codec='XVID')
        self.assertEqual(writer._codecs, ('XVID',))

    def test_default_uses_class_codecs(self):
        writer = make_writer()
        self.assertEqual(writer._codecs, _ConcreteWriter.CODECS)


class TestQOpenCVWriterOpen(unittest.TestCase):

    def test_open_returns_true_when_codec_works(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)):
            result = writer.open(_FRAME_COLOR)
        self.assertTrue(result)

    def test_open_returns_false_when_all_codecs_fail(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(False)):
            with self.assertLogs('QVideo.dvr.QOpenCVWriter', level='WARNING'):
                result = writer.open(_FRAME_COLOR)
        self.assertFalse(result)

    def test_open_sets_shape_on_success(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)):
            writer.open(_FRAME_COLOR)
        self.assertEqual(writer._shape, _FRAME_COLOR.shape)

    def test_open_does_not_set_shape_on_failure(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(False)):
            with self.assertLogs('QVideo.dvr.QOpenCVWriter', level='WARNING'):
                writer.open(_FRAME_COLOR)
        self.assertIsNone(writer._shape)

    def test_open_releases_failed_writer_before_trying_next(self):
        class _TwoCodecWriter(QOpenCVWriter):
            CODECS = ('FFV1', 'HFYU')

        writer = _TwoCodecWriter('test.avi', fps=30)
        failed_vw = make_mock_vw(False)
        with patch('cv2.VideoWriter',
                   side_effect=[failed_vw, make_mock_vw(True)]):
            writer.open(_FRAME_COLOR)
        failed_vw.release.assert_called_once()

    def test_open_color_flag_for_color_frame(self):
        writer = make_writer()
        with patch('cv2.VideoWriter') as mock_cls:
            mock_cls.return_value = make_mock_vw(True)
            writer.open(_FRAME_COLOR)
        self.assertTrue(mock_cls.call_args[0][4])

    def test_open_color_flag_for_gray_frame(self):
        writer = make_writer()
        with patch('cv2.VideoWriter') as mock_cls:
            mock_cls.return_value = make_mock_vw(True)
            writer.open(_FRAME_GRAY)
        self.assertFalse(mock_cls.call_args[0][4])

    def test_open_passes_correct_dimensions(self):
        writer = make_writer()
        with patch('cv2.VideoWriter') as mock_cls:
            mock_cls.return_value = make_mock_vw(True)
            writer.open(_FRAME_COLOR)
        w, h = mock_cls.call_args[0][3]
        self.assertEqual(w, 640)
        self.assertEqual(h, 480)

    def test_isopen_true_after_successful_open(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)):
            writer.open(_FRAME_COLOR)
        self.assertTrue(writer.isOpen())


class TestQOpenCVWriterInternalWrite(unittest.TestCase):

    def _open_writer(self, frame=None):
        writer = make_writer()
        mock_vw = make_mock_vw(True)
        if frame is None:
            frame = _FRAME_COLOR
        with patch('cv2.VideoWriter', return_value=mock_vw):
            writer.open(frame)
        return writer, mock_vw

    def test_write_color_frame_converts_rgb_to_bgr(self):
        writer, _ = self._open_writer()
        with patch('cv2.cvtColor', return_value=_FRAME_COLOR) as mock_cvt:
            writer._write(_FRAME_COLOR)
        mock_cvt.assert_called_once()
        _, code = mock_cvt.call_args[0]
        self.assertEqual(code, cv2.COLOR_RGB2BGR)

    def test_write_gray_frame_not_converted(self):
        writer, _ = self._open_writer(frame=_FRAME_GRAY)
        with patch('cv2.cvtColor') as mock_cvt:
            writer._write(_FRAME_GRAY)
        mock_cvt.assert_not_called()

    def test_write_shape_mismatch_emits_finished(self):
        writer, _ = self._open_writer()
        received = []
        writer.finished.connect(lambda: received.append(True))
        with self.assertLogs('QVideo.dvr.QOpenCVWriter', level='WARNING'):
            writer._write(np.zeros((240, 320, 3), dtype=np.uint8))
        self.assertEqual(len(received), 1)

    def test_write_shape_mismatch_does_not_write(self):
        writer, mock_vw = self._open_writer()
        with self.assertLogs('QVideo.dvr.QOpenCVWriter', level='WARNING'):
            writer._write(np.zeros((240, 320, 3), dtype=np.uint8))
        mock_vw.write.assert_not_called()


class TestQOpenCVWriterClose(unittest.TestCase):

    def test_close_releases_video_writer(self):
        writer = make_writer()
        mock_vw = make_mock_vw(True)
        with patch('cv2.VideoWriter', return_value=mock_vw):
            writer.open(_FRAME_COLOR)
        writer.close()
        mock_vw.release.assert_called_once()

    def test_close_sets_writer_to_none(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)):
            writer.open(_FRAME_COLOR)
        writer.close()
        self.assertIsNone(writer._writer)

    def test_close_clears_shape(self):
        writer = make_writer()
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)):
            writer.open(_FRAME_COLOR)
        writer.close()
        self.assertIsNone(writer._shape)

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
