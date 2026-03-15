'''Unit tests for SampleHold and QSampleHold.'''
import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from pyqtgraph.Qt import QtWidgets
from QVideo.filters.QSampleHold import SampleHold, QSampleHold


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_SHAPE = (4, 4)
_FRAME = np.full(_SHAPE, 100, dtype=np.uint8)
_DARK = np.zeros(_SHAPE, dtype=np.uint8)


def make_filter(**kwargs) -> SampleHold:
    return SampleHold(**kwargs)


def make_widget() -> QSampleHold:
    return QSampleHold(parent=None)


class TestSampleHold(unittest.TestCase):

    def test_default_order(self):
        f = make_filter()
        self.assertEqual(f.order, 1)

    def test_initial_count_equals_three_to_the_order(self):
        f = make_filter(order=1)
        self.assertEqual(f.count, 3)

    def test_count_for_order_two(self):
        f = make_filter(order=2)
        self.assertEqual(f.count, 9)

    def test_reset_restores_count(self):
        f = make_filter(order=1)
        f.count = 0
        f.reset()
        self.assertEqual(f.count, 3)

    def test_add_decrements_count(self):
        f = make_filter(order=1)
        initial = f.count
        f.add(_FRAME)
        self.assertEqual(f.count, initial - 1)

    def test_add_calls_super_while_counting(self):
        f = make_filter(order=1)
        with patch.object(f.__class__.__bases__[0], 'add') as mock_add:
            f.add(_FRAME)
        mock_add.assert_called_once_with(_FRAME)

    def test_add_does_not_call_super_after_count_zero(self):
        f = make_filter(order=1)
        # Drain the counter
        for _ in range(f.count):
            f.add(_FRAME)
        with patch.object(f.__class__.__bases__[0], 'add') as mock_add:
            f.add(_FRAME)
        mock_add.assert_not_called()

    def test_shape_change_triggers_reset(self):
        f = make_filter(order=1)
        # Drain the counter so count == 0
        for _ in range(f.count):
            f.add(_FRAME)
        self.assertEqual(f.count, 0)
        # Feed a frame with a different shape
        f.add(np.full((8, 8), 100, dtype=np.uint8))
        self.assertEqual(f.count, 3 - 1)  # reset then decremented once

    def test_add_stores_fg_after_count_zero(self):
        f = make_filter(order=1)
        for _ in range(f.count):
            f.add(_FRAME)
        foreground = np.full(_SHAPE, 50, dtype=np.uint8)
        f.add(foreground)
        expected = foreground - f.darkcount
        np.testing.assert_array_equal(f._fg, expected)

    def test_default_darkcount_is_zero(self):
        f = make_filter()
        self.assertEqual(f.darkcount, 0)

    def test_custom_darkcount(self):
        f = make_filter(darkcount=10)
        self.assertEqual(f.darkcount, 10)


class TestQSampleHold(unittest.TestCase):

    def test_is_qvideofilter(self):
        from QVideo.lib.VideoFilter import QVideoFilter
        widget = make_widget()
        self.assertIsInstance(widget, QVideoFilter)

    def test_filter_is_sample_hold(self):
        widget = make_widget()
        self.assertIsInstance(widget.filter, SampleHold)

    def test_title(self):
        widget = make_widget()
        self.assertEqual(widget.title(), 'Sample and Hold')

    def test_initially_unchecked(self):
        widget = make_widget()
        self.assertFalse(widget.isChecked())

    def test_has_reset_button(self):
        widget = make_widget()
        self.assertIsInstance(widget._reset_button, QtWidgets.QPushButton)

    def test_reset_button_label(self):
        widget = make_widget()
        self.assertEqual(widget._reset_button.text(), 'Reset')

    def test_reset_calls_filter_reset(self):
        widget = make_widget()
        widget.filter.count = 0
        widget.reset()
        self.assertEqual(widget.filter.count, 3 ** widget.filter.order)

    def test_reset_button_triggers_filter_reset(self):
        widget = make_widget()
        with patch.object(widget.filter, 'reset') as mock_reset:
            widget._reset_button.clicked.emit(False)
        mock_reset.assert_called_once()

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)


if __name__ == '__main__':
    unittest.main()
