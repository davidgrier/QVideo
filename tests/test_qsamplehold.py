'''Unit tests for SampleHold and QSampleHold.'''
import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from qtpy import QtWidgets
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
        self.assertEqual(f._count, 3)

    def test_count_for_order_two(self):
        f = make_filter(order=2)
        self.assertEqual(f._count, 9)

    def test_reset_restores_count(self):
        f = make_filter(order=1)
        f._count = 0
        f.reset()
        self.assertEqual(f._count, 3)

    def test_add_decrements_count(self):
        f = make_filter(order=1)
        initial = f._count
        f.add(_FRAME)
        self.assertEqual(f._count, initial - 1)

    def test_add_calls_super_while_counting(self):
        f = make_filter(order=1)
        with patch.object(f.__class__.__bases__[0], 'add') as mock_add:
            f.add(_FRAME)
        mock_add.assert_called_once_with(_FRAME)

    def test_add_does_not_call_super_after_count_zero(self):
        f = make_filter(order=1)
        # Drain the counter
        for _ in range(f._count):
            f.add(_FRAME)
        with patch.object(f.__class__.__bases__[0], 'add') as mock_add:
            f.add(_FRAME)
        mock_add.assert_not_called()

    def test_shape_change_triggers_reset(self):
        f = make_filter(order=1)
        # Drain the counter so count == 0
        for _ in range(f._count):
            f.add(_FRAME)
        self.assertEqual(f._count, 0)
        # Feed a frame with a different shape
        f.add(np.full((8, 8), 100, dtype=np.uint8))
        self.assertEqual(f._count, 3 - 1)  # reset then decremented once

    def test_add_stores_fg_after_count_zero(self):
        f = make_filter(order=1)
        for _ in range(f._count):
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
        from QVideo.lib.QVideoFilter import QVideoFilter
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

    def test_has_resetButton(self):
        widget = make_widget()
        self.assertIsInstance(widget._resetButton, QtWidgets.QPushButton)

    def test_resetButton_label(self):
        widget = make_widget()
        self.assertEqual(widget._resetButton.text(), 'Reset')

    def test_has_three_orderButtons(self):
        widget = make_widget()
        self.assertEqual(len(widget._orderButtons), 3)

    def test_order_button_labels(self):
        widget = make_widget()
        labels = [b.text() for b in widget._orderButtons]
        self.assertEqual(labels, ['1', '2', '3'])

    def test_default_order_button_checked(self):
        widget = make_widget()
        self.assertTrue(widget._orderButtons[0].isChecked())

    def test_set_order_when_checked_updates_filter(self):
        widget = make_widget()
        widget.setOrder(True, 2)
        self.assertEqual(widget.filter.order, 2)

    def test_set_order_when_checked_resets_count(self):
        widget = make_widget()
        widget.setOrder(True, 2)
        self.assertEqual(widget.filter._count, 9)

    def test_set_order_when_unchecked_does_not_update(self):
        widget = make_widget()
        widget.setOrder(True, 2)
        widget.setOrder(False, 2)
        self.assertEqual(widget.filter.order, 2)

    def test_reset_calls_filter_reset(self):
        widget = make_widget()
        widget.filter._count = 0
        widget.reset()
        self.assertEqual(widget.filter._count, 3 ** widget.filter.order)

    def test_resetButton_triggers_filter_reset(self):
        widget = make_widget()
        with patch.object(widget.filter, 'reset') as mock_reset:
            widget._resetButton.clicked.emit(False)
        mock_reset.assert_called_once()

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)


if __name__ == '__main__':
    unittest.main()
