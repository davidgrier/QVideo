'''Unit tests for QOpenCVWriter.'''
import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from qtpy import QtWidgets
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


def make_writer(filename='test.avi', **kwargs):
    return QOpenCVWriter(filename, fps=30, **kwargs)


class TestQOpenCVWriterClass(unittest.TestCase):

    def test_is_subclass_of_qvideowriter(self):
        self.assertTrue(issubclass(QOpenCVWriter, QVideoWriter))

    def test_codec_map_has_avi(self):
        self.assertIn('.avi', QOpenCVWriter.CODEC_MAP)

    def test_codec_map_has_mkv(self):
        self.assertIn('.mkv', QOpenCVWriter.CODEC_MAP)

    def test_codec_map_has_mp4(self):
        self.assertIn('.mp4', QOpenCVWriter.CODEC_MAP)

    def test_avi_prefers_ffv1(self):
        self.assertEqual(QOpenCVWriter.CODEC_MAP['.avi'][0], 'FFV1')

    def test_avi_fallback_is_hfyu(self):
        self.assertIn('HFYU', QOpenCVWriter.CODEC_MAP['.avi'])

    def test_mkv_prefers_ffv1(self):
        self.assertEqual(QOpenCVWriter.CODEC_MAP['.mkv'][0], 'FFV1')

    def test_mkv_fallback_is_hfyu(self):
        self.assertIn('HFYU', QOpenCVWriter.CODEC_MAP['.mkv'])

    def test_mp4_prefers_avc1(self):
        self.assertEqual(QOpenCVWriter.CODEC_MAP['.mp4'][0], 'avc1')

    def test_mp4_fallback_is_mp4v(self):
        self.assertIn('mp4v', QOpenCVWriter.CODEC_MAP['.mp4'])


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

    def test_codecs_from_avi_extension(self):
        writer = make_writer('test.avi')
        self.assertEqual(writer._codecs, QOpenCVWriter.CODEC_MAP['.avi'])

    def test_codecs_from_mkv_extension(self):
        writer = make_writer('test.mkv')
        self.assertEqual(writer._codecs, QOpenCVWriter.CODEC_MAP['.mkv'])

    def test_codecs_from_mp4_extension(self):
        writer = make_writer('test.mp4')
        self.assertEqual(writer._codecs, QOpenCVWriter.CODEC_MAP['.mp4'])

    def test_unknown_extension_gives_empty_codecs(self):
        writer = make_writer('test.xyz')
        self.assertEqual(writer._codecs, ())

    def test_custom_codec_overrides_map(self):
        writer = make_writer(codec='XVID')
        self.assertEqual(writer._codecs, ('XVID',))


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

    def test_open_tries_ffv1_first_for_avi(self):
        writer = make_writer('test.avi')
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)) as mock_cls:
            writer.open(_FRAME_COLOR)
        first_fourcc = mock_cls.call_args_list[0][0][1]
        self.assertEqual(first_fourcc, cv2.VideoWriter_fourcc(*'FFV1'))

    def test_open_falls_back_to_hfyu_for_avi(self):
        writer = make_writer('test.avi')
        with patch('cv2.VideoWriter',
                   side_effect=[make_mock_vw(False), make_mock_vw(True)]):
            result = writer.open(_FRAME_COLOR)
        self.assertTrue(result)

    def test_open_tries_avc1_first_for_mp4(self):
        writer = make_writer('test.mp4')
        with patch('cv2.VideoWriter', return_value=make_mock_vw(True)) as mock_cls:
            writer.open(_FRAME_COLOR)
        first_fourcc = mock_cls.call_args_list[0][0][1]
        self.assertEqual(first_fourcc, cv2.VideoWriter_fourcc(*'avc1'))

    def test_open_releases_failed_writer_before_trying_next(self):
        writer = make_writer()
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

    def test_custom_codec_used_directly(self):
        writer = make_writer(codec='XVID')
        with patch('cv2.VideoWriter') as mock_cls:
            mock_cls.return_value = make_mock_vw(True)
            writer.open(_FRAME_COLOR)
        self.assertEqual(mock_cls.call_count, 1)
        used_fourcc = mock_cls.call_args[0][1]
        self.assertEqual(used_fourcc, cv2.VideoWriter_fourcc(*'XVID'))


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
