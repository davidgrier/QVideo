'''Unit tests for ThresholdFilter and QThresholdFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
import cv2
from qtpy import QtWidgets
from QVideo.filters.threshold import ThresholdFilter, QThresholdFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_GRAY = np.zeros((480, 640), dtype=np.uint8)
_COLOR = np.zeros((480, 640, 3), dtype=np.uint8)


def make_filter(**kwargs) -> ThresholdFilter:
    return ThresholdFilter(**kwargs)


def make_widget() -> QThresholdFilter:
    return QThresholdFilter(parent=None)


class TestThresholdFilterThreshold(unittest.TestCase):

    def test_default_threshold(self):
        f = make_filter()
        self.assertEqual(f.threshold, 127)

    def test_custom_threshold(self):
        f = make_filter(threshold=200)
        self.assertEqual(f.threshold, 200)

    def test_threshold_clamped_high(self):
        f = make_filter(threshold=300)
        self.assertEqual(f.threshold, 255)

    def test_threshold_clamped_low(self):
        f = make_filter(threshold=-10)
        self.assertEqual(f.threshold, 0)

    def test_threshold_setter(self):
        f = make_filter()
        f.threshold = 50
        self.assertEqual(f.threshold, 50)

    def test_threshold_boundary_zero(self):
        self.assertEqual(make_filter(threshold=0).threshold, 0)

    def test_threshold_boundary_255(self):
        self.assertEqual(make_filter(threshold=255).threshold, 255)


class TestThresholdFilterMethod(unittest.TestCase):

    def test_default_method(self):
        self.assertEqual(make_filter().method, 'Global')

    def test_custom_method(self):
        self.assertEqual(make_filter(method='Otsu').method, 'Otsu')

    def test_method_setter_valid(self):
        f = make_filter()
        f.method = 'Adaptive Mean'
        self.assertEqual(f.method, 'Adaptive Mean')

    def test_method_setter_invalid(self):
        f = make_filter()
        with self.assertRaises(ValueError):
            f.method = 'NoSuchMethod'

    def test_all_methods_accepted(self):
        for m in ThresholdFilter.METHODS:
            f = make_filter()
            f.method = m
            self.assertEqual(f.method, m)


class TestThresholdFilterBlockSize(unittest.TestCase):

    def test_default_block_size(self):
        self.assertEqual(make_filter().block_size, 11)

    def test_custom_block_size(self):
        self.assertEqual(make_filter(block_size=15).block_size, 15)

    def test_block_size_enforces_odd_even_input(self):
        f = make_filter(block_size=10)
        self.assertEqual(f.block_size % 2, 1)

    def test_block_size_enforces_minimum(self):
        f = make_filter(block_size=1)
        self.assertGreaterEqual(f.block_size, 3)

    def test_block_size_odd_preserved(self):
        f = make_filter(block_size=11)
        self.assertEqual(f.block_size, 11)


class TestThresholdFilterC(unittest.TestCase):

    def test_default_C(self):
        self.assertEqual(make_filter().C, 2)

    def test_custom_C(self):
        self.assertEqual(make_filter(C=5).C, 5)

    def test_C_setter(self):
        f = make_filter()
        f.C = 10
        self.assertEqual(f.C, 10)

    def test_C_negative(self):
        f = make_filter(C=-3)
        self.assertEqual(f.C, -3)


class TestThresholdFilterGet(unittest.TestCase):

    def test_get_returns_none_before_add(self):
        self.assertIsNone(make_filter().get())

    def test_get_returns_ndarray(self):
        f = make_filter()
        f.add(_GRAY)
        self.assertIsInstance(f.get(), np.ndarray)

    def test_get_global_calls_cv2_threshold(self):
        f = make_filter(threshold=100)
        f.add(_GRAY)
        _THRESH = np.zeros_like(_GRAY)
        with patch('cv2.threshold', return_value=(100, _THRESH)) as mock_t:
            f.get()
        mock_t.assert_called_once_with(_GRAY, 100, 255, cv2.THRESH_BINARY)

    def test_get_otsu_calls_cv2_threshold_with_otsu_flag(self):
        f = make_filter(method='Otsu')
        f.add(_GRAY)
        _THRESH = np.zeros_like(_GRAY)
        with patch('cv2.threshold', return_value=(0, _THRESH)) as mock_t:
            f.get()
        _, _, _, flags = mock_t.call_args[0]
        self.assertTrue(flags & cv2.THRESH_OTSU)

    def test_get_adaptive_mean_calls_adaptiveThreshold(self):
        f = make_filter(method='Adaptive Mean', block_size=11, C=2)
        f.add(_GRAY)
        _THRESH = np.zeros_like(_GRAY)
        with patch('cv2.adaptiveThreshold', return_value=_THRESH) as mock_t:
            f.get()
        mock_t.assert_called_once_with(
            _GRAY, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY, 11, 2)

    def test_get_adaptive_gaussian_calls_adaptiveThreshold(self):
        f = make_filter(method='Adaptive Gaussian', block_size=11, C=2)
        f.add(_GRAY)
        _THRESH = np.zeros_like(_GRAY)
        with patch('cv2.adaptiveThreshold', return_value=_THRESH) as mock_t:
            f.get()
        mock_t.assert_called_once_with(
            _GRAY, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2)

    def test_color_frame_converted_to_grayscale(self):
        f = make_filter()
        f.add(_COLOR)
        _THRESH = np.zeros((_COLOR.shape[0], _COLOR.shape[1]), dtype=np.uint8)
        with patch('cv2.threshold', return_value=(127, _THRESH)) as mock_t:
            f.get()
        input_arg = mock_t.call_args[0][0]
        self.assertEqual(input_arg.ndim, 2)

    def test_call_applies_threshold(self):
        f = make_filter()
        _THRESH = np.zeros_like(_GRAY)
        with patch('cv2.threshold', return_value=(127, _THRESH)):
            result = f(_GRAY)
        self.assertIsInstance(result, np.ndarray)


class TestQThresholdFilterInit(unittest.TestCase):

    def test_filter_is_threshold_filter(self):
        self.assertIsInstance(make_widget().filter, ThresholdFilter)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Threshold')


class TestQThresholdFilterSetMethod(unittest.TestCase):

    def test_set_method_updates_filter(self):
        w = make_widget()
        w._setMethod('Otsu')
        self.assertEqual(w.filter.method, 'Otsu')

    def test_global_shows_level_hides_block_c(self):
        w = make_widget()
        w._setMethod('Global')
        self.assertFalse(w._levelBox.isHidden())
        self.assertTrue(w._blockBox.isHidden())
        self.assertTrue(w._cBox.isHidden())

    def test_otsu_hides_all_param_boxes(self):
        w = make_widget()
        w._setMethod('Otsu')
        self.assertTrue(w._levelBox.isHidden())
        self.assertTrue(w._blockBox.isHidden())
        self.assertTrue(w._cBox.isHidden())

    def test_adaptive_mean_shows_block_c(self):
        w = make_widget()
        w._setMethod('Adaptive Mean')
        self.assertTrue(w._levelBox.isHidden())
        self.assertFalse(w._blockBox.isHidden())
        self.assertFalse(w._cBox.isHidden())

    def test_adaptive_gaussian_shows_block_c(self):
        w = make_widget()
        w._setMethod('Adaptive Gaussian')
        self.assertTrue(w._levelBox.isHidden())
        self.assertFalse(w._blockBox.isHidden())
        self.assertFalse(w._cBox.isHidden())


class TestQThresholdFilterSetLevel(unittest.TestCase):

    def test_set_level_updates_filter(self):
        w = make_widget()
        w._setLevel(100)
        self.assertEqual(w.filter.threshold, 100)

    def test_set_level_snaps_spinbox_to_clamped_value(self):
        w = make_widget()
        w._setLevel(300)
        self.assertEqual(w._levelBox.value(), 255)

    def test_level_spinbox_lower_bound(self):
        w = make_widget()
        self.assertEqual(w._levelBox.opts['bounds'][0], 0)

    def test_level_spinbox_upper_bound(self):
        w = make_widget()
        self.assertEqual(w._levelBox.opts['bounds'][1], 255)


class TestQThresholdFilterSetBlockSize(unittest.TestCase):

    def test_set_block_size_updates_filter(self):
        w = make_widget()
        w._setBlockSize(15)
        self.assertEqual(w.filter.block_size, 15)

    def test_set_block_size_snaps_spinbox_to_odd(self):
        w = make_widget()
        w._setBlockSize(10)
        self.assertEqual(w._blockBox.value() % 2, 1)


class TestQThresholdFilterSetC(unittest.TestCase):

    def test_set_c_updates_filter(self):
        w = make_widget()
        w._setC(7)
        self.assertEqual(w.filter.C, 7)


class TestQThresholdFilterCall(unittest.TestCase):

    def test_call_unchecked_returns_frame_unchanged(self):
        w = make_widget()
        result = w(_GRAY)
        np.testing.assert_array_equal(result, _GRAY)

    def test_call_checked_applies_threshold(self):
        w = make_widget()
        w.setChecked(True)
        _THRESH = np.zeros_like(_GRAY)
        with patch('cv2.threshold', return_value=(127, _THRESH)) as mock_t:
            w(_GRAY)
        mock_t.assert_called_once()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
