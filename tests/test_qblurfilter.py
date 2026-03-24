'''Unit tests for BlurFilter and QBlurFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from pyqtgraph.Qt import QtWidgets
from QVideo.filters.QBlurFilter import BlurFilter, QBlurFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640), dtype=np.uint8)


def make_filter(**kwargs) -> BlurFilter:
    return BlurFilter(**kwargs)


def make_widget() -> QBlurFilter:
    return QBlurFilter(parent=None)


class TestBlurFilter(unittest.TestCase):

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

    def test_get_returns_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.get())

    def test_get_calls_gaussian_blur(self):
        f = make_filter(width=5)
        f.add(_FRAME)
        with patch('cv2.GaussianBlur', return_value=_FRAME) as mock_blur:
            f.get()
        mock_blur.assert_called_once_with(_FRAME, (5, 5), 0)

    def test_get_returns_ndarray(self):
        f = make_filter()
        f.add(_FRAME)
        with patch('cv2.GaussianBlur', return_value=_FRAME):
            result = f.get()
        self.assertIsInstance(result, np.ndarray)

    def test_call_applies_blur(self):
        f = make_filter()
        with patch('cv2.GaussianBlur', return_value=_FRAME) as mock_blur:
            f(_FRAME)
        mock_blur.assert_called_once()

    def test_kernel_size_matches_width(self):
        f = make_filter(width=7)
        f.add(_FRAME)
        with patch('cv2.GaussianBlur', return_value=_FRAME) as mock_blur:
            f.get()
        _, ksize, _ = mock_blur.call_args[0]
        self.assertEqual(ksize, (7, 7))


class TestQBlurFilter(unittest.TestCase):

    def test_is_qvideofilter(self):
        from QVideo.lib.QVideoFilter import QVideoFilter
        widget = make_widget()
        self.assertIsInstance(widget, QVideoFilter)

    def test_filter_is_blur_filter(self):
        widget = make_widget()
        self.assertIsInstance(widget.filter, BlurFilter)

    def test_title(self):
        widget = make_widget()
        self.assertEqual(widget.title(), 'Gaussian Blur')

    def test_initially_unchecked(self):
        widget = make_widget()
        self.assertFalse(widget.isChecked())

    def test_set_width_updates_filter(self):
        widget = make_widget()
        widget.setWidth(9)
        self.assertEqual(widget.filter.width, 9)

    def test_set_width_snaps_spinbox_to_corrected_value(self):
        widget = make_widget()
        widget.setWidth(8)
        self.assertEqual(widget._spinbox.value(), 9)

    def test_set_width_snap_does_not_recurse(self):
        widget = make_widget()
        call_count = []
        original = widget.setWidth
        def counting_setWidth(w):
            call_count.append(w)
            original(w)
        widget.setWidth = counting_setWidth
        widget._spinbox.valueChanged.disconnect()
        widget._spinbox.valueChanged.connect(widget.setWidth)
        widget._spinbox.setValue(8)
        self.assertEqual(len(call_count), 1)

    def test_spinbox_minimum_is_three(self):
        widget = make_widget()
        self.assertEqual(widget._spinbox.opts['bounds'][0], 3)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)

    def test_call_when_checked_applies_blur(self):
        widget = make_widget()
        widget.setChecked(True)
        with patch('cv2.GaussianBlur', return_value=_FRAME) as mock_blur:
            widget(_FRAME)
        mock_blur.assert_called_once()


if __name__ == '__main__':
    unittest.main()
