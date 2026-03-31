'''Unit tests for EdgeFilter and QEdgeFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtWidgets
from QVideo.filters.QEdgeFilter import EdgeFilter, QEdgeFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_RGB = np.zeros((4, 4, 3), dtype=np.uint8)
_GRAY = np.zeros((4, 4), dtype=np.uint8)
_EDGE = np.ones((4, 4), dtype=np.uint8)


def make_filter(**kwargs) -> EdgeFilter:
    return EdgeFilter(**kwargs)


def make_widget() -> QEdgeFilter:
    return QEdgeFilter(parent=None)


class TestEdgeFilter(unittest.TestCase):

    def test_default_low(self):
        f = make_filter()
        self.assertEqual(f.low, 50)

    def test_default_high(self):
        f = make_filter()
        self.assertEqual(f.high, 150)

    def test_custom_low(self):
        f = make_filter(low=30)
        self.assertEqual(f.low, 30)

    def test_custom_high(self):
        f = make_filter(high=200)
        self.assertEqual(f.high, 200)

    def test_low_setter_valid(self):
        f = make_filter()
        f.low = 10
        self.assertEqual(f.low, 10)

    def test_high_setter_valid(self):
        f = make_filter()
        f.high = 200
        self.assertEqual(f.high, 200)

    def test_low_clamped_to_one(self):
        f = make_filter()
        f.low = 0
        self.assertEqual(f.low, 1)

    def test_high_clamped_to_two(self):
        f = make_filter(low=1)
        f.high = 1
        self.assertEqual(f.high, 2)  # clamped to minimum of 2

    def test_low_rejected_when_gte_high(self):
        f = make_filter(low=50, high=150)
        f.low = 150
        self.assertEqual(f.low, 50)  # unchanged

    def test_high_rejected_when_lte_low(self):
        f = make_filter(low=50, high=150)
        f.high = 50
        self.assertEqual(f.high, 150)  # unchanged

    def test_low_rejected_logs_warning(self):
        f = make_filter(low=50, high=150)
        with self.assertLogs('QVideo.filters.QEdgeFilter', level='WARNING'):
            f.low = 200

    def test_high_rejected_logs_warning(self):
        f = make_filter(low=50, high=150)
        with self.assertLogs('QVideo.filters.QEdgeFilter', level='WARNING'):
            f.high = 10

    def test_get_returns_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.get())

    def test_add_rgb_converts_to_gray(self):
        f = make_filter()
        f.add(_RGB)
        self.assertEqual(f.data.ndim, 2)

    def test_add_gray_stored_unchanged(self):
        f = make_filter()
        f.add(_GRAY)
        np.testing.assert_array_equal(f.data, _GRAY)

    def test_get_calls_canny(self):
        f = make_filter(low=50, high=150)
        f.add(_GRAY)
        with patch('cv2.Canny', return_value=_EDGE) as mock_canny:
            f.get()
        mock_canny.assert_called_once_with(_GRAY, 50, 150)

    def test_get_returns_ndarray(self):
        f = make_filter()
        f.add(_GRAY)
        with patch('cv2.Canny', return_value=_EDGE):
            result = f.get()
        self.assertIsInstance(result, np.ndarray)

    def test_call_applies_edge_detection(self):
        f = make_filter()
        with patch('cv2.Canny', return_value=_EDGE) as mock_canny:
            f(_GRAY)
        mock_canny.assert_called_once()


class TestQEdgeFilter(unittest.TestCase):

    def test_is_qvideofilter(self):
        from QVideo.lib.QVideoFilter import QVideoFilter
        widget = make_widget()
        self.assertIsInstance(widget, QVideoFilter)

    def test_filter_is_edge_filter(self):
        widget = make_widget()
        self.assertIsInstance(widget.filter, EdgeFilter)

    def test_title(self):
        widget = make_widget()
        self.assertEqual(widget.title(), 'Canny Edge Detection')

    def test_initially_unchecked(self):
        widget = make_widget()
        self.assertFalse(widget.isChecked())

    def test_has_lowSpinbox(self):
        widget = make_widget()
        self.assertIsNotNone(widget._lowSpinbox)

    def test_has_highSpinbox(self):
        widget = make_widget()
        self.assertIsNotNone(widget._highSpinbox)

    def test_set_low_updates_filter(self):
        widget = make_widget()
        widget.setLow(20)
        self.assertEqual(widget.filter.low, 20)

    def test_set_high_updates_filter(self):
        widget = make_widget()
        widget.setHigh(200)
        self.assertEqual(widget.filter.high, 200)

    def test_set_low_snaps_spinbox(self):
        widget = make_widget()
        widget.setLow(20)
        self.assertEqual(widget._lowSpinbox.value(), 20)

    def test_set_high_snaps_spinbox(self):
        widget = make_widget()
        widget.setHigh(200)
        self.assertEqual(widget._highSpinbox.value(), 200)

    def test_set_low_rejected_snaps_spinbox_back(self):
        widget = make_widget()
        original_low = widget.filter.low
        with self.assertLogs('QVideo.filters.QEdgeFilter', level='WARNING'):
            widget.setLow(widget.filter.high + 10)
        self.assertEqual(widget._lowSpinbox.value(), original_low)

    def test_set_high_rejected_snaps_spinbox_back(self):
        widget = make_widget()
        original_high = widget.filter.high
        with self.assertLogs('QVideo.filters.QEdgeFilter', level='WARNING'):
            widget.setHigh(widget.filter.low - 1)
        self.assertEqual(widget._highSpinbox.value(), original_high)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_RGB)
        np.testing.assert_array_equal(result, _RGB)

    def test_call_when_checked_applies_filter(self):
        widget = make_widget()
        widget.setChecked(True)
        with patch('cv2.Canny', return_value=_EDGE) as mock_canny:
            widget(_GRAY)
        mock_canny.assert_called_once()


if __name__ == '__main__':
    unittest.main()
