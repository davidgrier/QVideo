'''Unit tests for ThresholdFilter and QThresholdFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
import cv2
from qtpy import QtWidgets
from QVideo.filters.QThresholdFilter import ThresholdFilter, QThresholdFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640), dtype=np.uint8)


def make_filter(**kwargs) -> ThresholdFilter:
    return ThresholdFilter(**kwargs)


def make_widget() -> QThresholdFilter:
    return QThresholdFilter(parent=None)


class TestThresholdFilter(unittest.TestCase):

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
        f = make_filter(threshold=0)
        self.assertEqual(f.threshold, 0)

    def test_threshold_boundary_255(self):
        f = make_filter(threshold=255)
        self.assertEqual(f.threshold, 255)

    def test_get_returns_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.get())

    def test_get_calls_cv2_threshold(self):
        f = make_filter(threshold=100)
        f.add(_FRAME)
        _THRESH = np.zeros_like(_FRAME)
        with patch('cv2.threshold', return_value=(100, _THRESH)) as mock_thresh:
            f.get()
        mock_thresh.assert_called_once_with(_FRAME, 100, 255, cv2.THRESH_BINARY)

    def test_get_returns_ndarray(self):
        f = make_filter()
        f.add(_FRAME)
        result = f.get()
        self.assertIsInstance(result, np.ndarray)

    def test_call_applies_threshold(self):
        f = make_filter()
        _THRESH = np.zeros_like(_FRAME)
        with patch('cv2.threshold', return_value=(127, _THRESH)) as mock_thresh:
            f(_FRAME)
        mock_thresh.assert_called_once()

    def test_threshold_value_passed_to_cv2(self):
        f = make_filter(threshold=80)
        f.add(_FRAME)
        _THRESH = np.zeros_like(_FRAME)
        with patch('cv2.threshold', return_value=(80, _THRESH)) as mock_thresh:
            f.get()
        _, thresh_val, max_val, _ = mock_thresh.call_args[0]
        self.assertEqual(thresh_val, 80)
        self.assertEqual(max_val, 255)


class TestQThresholdFilter(unittest.TestCase):

    def test_is_qvideofilter(self):
        from QVideo.lib.QVideoFilter import QVideoFilter
        widget = make_widget()
        self.assertIsInstance(widget, QVideoFilter)

    def test_filter_is_threshold_filter(self):
        widget = make_widget()
        self.assertIsInstance(widget.filter, ThresholdFilter)

    def test_title(self):
        widget = make_widget()
        self.assertEqual(widget.title(), 'Threshold')

    def test_initially_unchecked(self):
        widget = make_widget()
        self.assertFalse(widget.isChecked())

    def test_set_threshold_updates_filter(self):
        widget = make_widget()
        widget.setThreshold(100)
        self.assertEqual(widget.filter.threshold, 100)

    def test_set_threshold_clamped_high(self):
        widget = make_widget()
        widget.setThreshold(300)
        self.assertEqual(widget.filter.threshold, 255)

    def test_set_threshold_snaps_spinbox_to_clamped_value(self):
        widget = make_widget()
        widget.setThreshold(300)
        self.assertEqual(widget._spinbox.value(), 255)

    def test_set_threshold_snap_does_not_recurse(self):
        widget = make_widget()
        call_count = []
        original = widget.setThreshold
        def counting_setThreshold(v):
            call_count.append(v)
            original(v)
        widget.setThreshold = counting_setThreshold
        widget._spinbox.valueChanged.disconnect()
        widget._spinbox.valueChanged.connect(widget.setThreshold)
        widget._spinbox.setValue(200)
        self.assertEqual(len(call_count), 1)

    def test_spinbox_lower_bound(self):
        widget = make_widget()
        self.assertEqual(widget._spinbox.opts['bounds'][0], 0)

    def test_spinbox_upper_bound(self):
        widget = make_widget()
        self.assertEqual(widget._spinbox.opts['bounds'][1], 255)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)

    def test_call_when_checked_applies_threshold(self):
        widget = make_widget()
        widget.setChecked(True)
        _THRESH = np.zeros_like(_FRAME)
        with patch('cv2.threshold', return_value=(127, _THRESH)) as mock_thresh:
            widget(_FRAME)
        mock_thresh.assert_called_once()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
