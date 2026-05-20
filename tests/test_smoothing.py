'''Unit tests for SmoothingFilter and QSmoothingFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.filters.smoothing import SmoothingFilter, QSmoothingFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640), dtype=np.uint8)


def make_filter(**kwargs) -> SmoothingFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return SmoothingFilter(**kwargs)


def make_widget() -> QSmoothingFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return QSmoothingFilter(parent=None)


# ---------------------------------------------------------------------------
# SmoothingFilter — width property
# ---------------------------------------------------------------------------

class TestSmoothingFilterWidth(unittest.TestCase):

    def test_default_width(self):
        f = make_filter()
        self.assertEqual(f.width, 15)

    def test_custom_width(self):
        f = make_filter(width=7)
        self.assertEqual(f.width, 7)

    def test_odd_width_unchanged(self):
        f = make_filter(width=9)
        self.assertEqual(f.width, 9)

    def test_even_width_rounded_up(self):
        f = make_filter(width=8)
        self.assertEqual(f.width, 9)

    def test_negative_width_clamped_to_one(self):
        f = make_filter(width=-5)
        self.assertEqual(f.width, 1)

    def test_zero_width_clamped_to_one(self):
        f = make_filter(width=0)
        self.assertEqual(f.width, 1)

    def test_width_one_is_valid(self):
        f = make_filter(width=1)
        self.assertEqual(f.width, 1)

    def test_width_setter_odd(self):
        f = make_filter()
        f.width = 11
        self.assertEqual(f.width, 11)

    def test_width_setter_even(self):
        f = make_filter()
        f.width = 10
        self.assertEqual(f.width, 11)


# ---------------------------------------------------------------------------
# SmoothingFilter — method property
# ---------------------------------------------------------------------------

class TestSmoothingFilterMethod(unittest.TestCase):

    def test_default_method_is_gaussian(self):
        f = make_filter()
        self.assertEqual(f.method, 'gaussian')

    def test_custom_method_median(self):
        f = make_filter(method='median')
        self.assertEqual(f.method, 'median')

    def test_method_setter(self):
        f = make_filter()
        f.method = 'median'
        self.assertEqual(f.method, 'median')

    def test_invalid_method_raises(self):
        with self.assertRaises(ValueError):
            make_filter(method='box')

    def test_invalid_method_setter_raises(self):
        f = make_filter()
        with self.assertRaises(ValueError):
            f.method = 'bilateral'


# ---------------------------------------------------------------------------
# SmoothingFilter — process()
# ---------------------------------------------------------------------------

class TestSmoothingFilterProcess(unittest.TestCase):

    def test_process_returns_ndarray(self):
        f = make_filter()
        with patch('cv2.GaussianBlur', return_value=_FRAME):
            result = f.process(_FRAME)
        self.assertIsInstance(result, np.ndarray)

    def test_kernel_size_matches_width(self):
        f = make_filter(width=7)
        with patch('cv2.GaussianBlur', return_value=_FRAME) as mock_blur:
            f.process(_FRAME)
        _, ksize, _ = mock_blur.call_args[0]
        self.assertEqual(ksize, (7, 7))

    def test_call_applies_gaussian(self):
        f = make_filter(method='gaussian')
        with patch('cv2.GaussianBlur', return_value=_FRAME) as mock_blur:
            f(_FRAME)
        mock_blur.assert_called_once()

    def test_call_applies_median(self):
        f = make_filter(method='median')
        with patch('cv2.medianBlur', return_value=_FRAME) as mock_blur:
            f(_FRAME)
        mock_blur.assert_called_once()


# ---------------------------------------------------------------------------
# QSmoothingFilter
# ---------------------------------------------------------------------------

class TestQSmoothingFilter(unittest.TestCase):

    def test_filter_is_smoothing_filter(self):
        widget = make_widget()
        self.assertIsInstance(widget.filter, SmoothingFilter)

    def test_title(self):
        widget = make_widget()
        self.assertEqual(widget.title(), 'Smoothing')

    def test_default_method_is_gaussian(self):
        widget = make_widget()
        self.assertEqual(widget._methodBox.currentText(), 'Gaussian')

    def test_set_method_updates_filter(self):
        widget = make_widget()
        widget._methodBox.setCurrentText('Median')
        self.assertEqual(widget.filter.method, 'median')

    def test_set_width_updates_filter(self):
        widget = make_widget()
        widget._setWidth(9)
        self.assertEqual(widget.filter.width, 9)

    def test_set_width_snaps_spinbox_to_corrected_value(self):
        widget = make_widget()
        widget._setWidth(8)
        self.assertEqual(widget._spinbox.value(), 9)

    def test_spinbox_minimum_is_three(self):
        widget = make_widget()
        self.assertEqual(widget._spinbox.opts['bounds'][0], 3)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)

    def test_call_when_checked_applies_gaussian(self):
        widget = make_widget()
        widget.setChecked(True)
        with patch('cv2.GaussianBlur', return_value=_FRAME) as mock_blur:
            widget(_FRAME)
        mock_blur.assert_called_once()

    def test_call_when_checked_applies_median(self):
        widget = make_widget()
        widget.setChecked(True)
        widget._methodBox.setCurrentText('Median')
        with patch('cv2.medianBlur', return_value=_FRAME) as mock_blur:
            widget(_FRAME)
        mock_blur.assert_called_once()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
