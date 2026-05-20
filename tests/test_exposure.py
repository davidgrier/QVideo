'''Tests for ExposureFilter and QExposureFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.filters.exposure import ExposureFilter, QExposureFilter

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_GRAY = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
_COLOR = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)


def make_filter(**kwargs) -> ExposureFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return ExposureFilter(**kwargs)


def make_widget() -> QExposureFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return QExposureFilter(parent=None)


class TestExposureFilterIsAsync(unittest.TestCase):

    def test_is_async_video_filter(self):
        f = make_filter()
        self.assertIsInstance(f, AsyncVideoFilter)


class TestExposureFilterDefaults(unittest.TestCase):

    def setUp(self):
        self.f = make_filter()

    def test_default_method(self):
        self.assertEqual(self.f.method, 'Log')

    def test_default_cutoff(self):
        self.assertAlmostEqual(self.f.cutoff, 128.0)

    def test_default_gain(self):
        self.assertAlmostEqual(self.f.gain, 10.0)

    def test_default_clip_limit(self):
        self.assertAlmostEqual(self.f.clip_limit, 2.0)

    def test_default_tile_size(self):
        self.assertEqual(self.f.tile_size, 8)


class TestExposureFilterMethod(unittest.TestCase):

    def setUp(self):
        self.f = make_filter()

    def test_invalid_method_ignored(self):
        self.f.method = 'Invalid'
        self.assertEqual(self.f.method, 'Log')

    def test_set_method_sigmoid(self):
        self.f.method = 'Sigmoid'
        self.assertEqual(self.f.method, 'Sigmoid')

    def test_set_method_clahe(self):
        self.f.method = 'CLAHE'
        self.assertEqual(self.f.method, 'CLAHE')


class TestExposureFilterProperties(unittest.TestCase):

    def setUp(self):
        self.f = make_filter()

    def test_cutoff_clamps_low(self):
        self.f.cutoff = -10.0
        self.assertGreaterEqual(self.f.cutoff, 0.0)

    def test_cutoff_clamps_high(self):
        self.f.cutoff = 300.0
        self.assertLessEqual(self.f.cutoff, 255.0)

    def test_gain_clamps_to_minimum(self):
        self.f.gain = 0.0
        self.assertGreaterEqual(self.f.gain, 0.1)

    def test_clip_limit_clamps_to_minimum(self):
        self.f.clip_limit = 0.0
        self.assertGreaterEqual(self.f.clip_limit, 0.1)

    def test_tile_size_clamps_to_minimum(self):
        self.f.tile_size = 0
        self.assertGreaterEqual(self.f.tile_size, 1)

    def test_clahe_rebuilt_on_clip_limit_change(self):
        clahe_before = id(self.f._clahe)
        self.f.clip_limit = 4.0
        self.assertNotEqual(id(self.f._clahe), clahe_before)

    def test_clahe_rebuilt_on_tile_size_change(self):
        clahe_before = id(self.f._clahe)
        self.f.tile_size = 16
        self.assertNotEqual(id(self.f._clahe), clahe_before)


class TestExposureFilterProcess(unittest.TestCase):

    def setUp(self):
        self.f = make_filter()

    def test_log_grayscale_shape(self):
        result = self.f.process(_GRAY)
        self.assertEqual(result.shape, _GRAY.shape)

    def test_log_grayscale_dtype(self):
        result = self.f.process(_GRAY)
        self.assertEqual(result.dtype, np.uint8)

    def test_log_color_shape(self):
        result = self.f.process(_COLOR)
        self.assertEqual(result.shape, _COLOR.shape)

    def test_log_color_dtype(self):
        result = self.f.process(_COLOR)
        self.assertEqual(result.dtype, np.uint8)

    def test_log_black_stays_black(self):
        black = np.zeros((8, 8), dtype=np.uint8)
        result = self.f.process(black)
        np.testing.assert_array_equal(result, 0)

    def test_log_white_stays_white(self):
        white = np.full((8, 8), 255, dtype=np.uint8)
        result = self.f.process(white)
        np.testing.assert_array_equal(result, 255)

    def test_sigmoid_grayscale_shape(self):
        self.f.method = 'Sigmoid'
        result = self.f.process(_GRAY)
        self.assertEqual(result.shape, _GRAY.shape)

    def test_sigmoid_color_shape(self):
        self.f.method = 'Sigmoid'
        result = self.f.process(_COLOR)
        self.assertEqual(result.shape, _COLOR.shape)

    def test_sigmoid_dtype(self):
        self.f.method = 'Sigmoid'
        result = self.f.process(_GRAY)
        self.assertEqual(result.dtype, np.uint8)

    def test_clahe_grayscale_shape(self):
        self.f.method = 'CLAHE'
        result = self.f.process(_GRAY)
        self.assertEqual(result.shape, _GRAY.shape)

    def test_clahe_color_shape(self):
        self.f.method = 'CLAHE'
        result = self.f.process(_COLOR)
        self.assertEqual(result.shape, _COLOR.shape)

    def test_clahe_dtype(self):
        self.f.method = 'CLAHE'
        result = self.f.process(_GRAY)
        self.assertEqual(result.dtype, np.uint8)


class TestExposureFilterToCode(unittest.TestCase):

    def setUp(self):
        self.f = make_filter()

    def test_to_code_log(self):
        from QVideo.lib.QVideoFilter import FilterCode
        self.f.method = 'Log'
        code = self.f.to_code()
        self.assertIsInstance(code, FilterCode)
        self.assertIn('import numpy as np', code.imports)
        self.assertIn('log', code.comment)

    def test_to_code_sigmoid(self):
        from QVideo.lib.QVideoFilter import FilterCode
        self.f.method = 'Sigmoid'
        code = self.f.to_code()
        self.assertIsInstance(code, FilterCode)
        self.assertIn('import numpy as np', code.imports)
        self.assertIn('sigmoid', code.comment)

    def test_to_code_clahe(self):
        from QVideo.lib.QVideoFilter import FilterCode
        self.f.method = 'CLAHE'
        code = self.f.to_code()
        self.assertIsInstance(code, FilterCode)
        self.assertIn('import cv2', code.imports)
        self.assertIn('CLAHE', code.comment)


class TestQExposureFilter(unittest.TestCase):

    def setUp(self):
        self.w = make_widget()

    def test_filter_instance(self):
        self.assertIsInstance(self.w.filter, ExposureFilter)

    def test_method_box_exists(self):
        self.assertTrue(hasattr(self.w, '_methodBox'))

    def test_sigmoid_spinboxes_hidden_for_log(self):
        self.w._setMethod('Log')
        self.assertTrue(self.w._cutoffBox.isHidden())
        self.assertTrue(self.w._gainBox.isHidden())

    def test_clahe_spinboxes_hidden_for_log(self):
        self.w._setMethod('Log')
        self.assertTrue(self.w._clipBox.isHidden())
        self.assertTrue(self.w._tileBox.isHidden())

    def test_sigmoid_spinboxes_visible_for_sigmoid(self):
        self.w._setMethod('Sigmoid')
        self.assertFalse(self.w._cutoffBox.isHidden())
        self.assertFalse(self.w._gainBox.isHidden())

    def test_clahe_spinboxes_hidden_for_sigmoid(self):
        self.w._setMethod('Sigmoid')
        self.assertTrue(self.w._clipBox.isHidden())
        self.assertTrue(self.w._tileBox.isHidden())

    def test_clahe_spinboxes_visible_for_clahe(self):
        self.w._setMethod('CLAHE')
        self.assertFalse(self.w._clipBox.isHidden())
        self.assertFalse(self.w._tileBox.isHidden())

    def test_sigmoid_spinboxes_hidden_for_clahe(self):
        self.w._setMethod('CLAHE')
        self.assertTrue(self.w._cutoffBox.isHidden())
        self.assertTrue(self.w._gainBox.isHidden())

    def test_set_method_updates_filter(self):
        self.w._setMethod('Sigmoid')
        self.assertEqual(self.w.filter.method, 'Sigmoid')

    def test_set_cutoff_updates_filter(self):
        self.w._setCutoff(100.0)
        self.assertAlmostEqual(self.w.filter.cutoff, 100.0)

    def test_set_gain_updates_filter(self):
        self.w._setGain(5.0)
        self.assertAlmostEqual(self.w.filter.gain, 5.0)

    def test_set_clip_limit_updates_filter(self):
        self.w._setClipLimit(3.0)
        self.assertAlmostEqual(self.w.filter.clip_limit, 3.0)

    def test_set_tile_size_updates_filter(self):
        self.w._setTileSize(16)
        self.assertEqual(self.w.filter.tile_size, 16)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
