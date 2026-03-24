'''Unit tests for RGBFilter and QRGBFilter.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtWidgets
from QVideo.filters.QRGBFilter import RGBFilter, QRGBFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# 3-channel frame with distinct per-channel values
_RGB = np.zeros((4, 4, 3), dtype=np.uint8)
_RGB[:, :, 0] = 10   # red
_RGB[:, :, 1] = 20   # green
_RGB[:, :, 2] = 30   # blue

_GRAY = np.full((4, 4), 42, dtype=np.uint8)


def make_filter(**kwargs) -> RGBFilter:
    return RGBFilter(**kwargs)


def make_widget() -> QRGBFilter:
    return QRGBFilter(parent=None)


class TestRGBFilter(unittest.TestCase):

    def test_default_channel(self):
        f = make_filter()
        self.assertEqual(f.channel, 0)

    def test_custom_channel(self):
        f = make_filter(channel=2)
        self.assertEqual(f.channel, 2)

    def test_channel_setter_valid(self):
        f = make_filter()
        for c in (0, 1, 2):
            f.channel = c
            self.assertEqual(f.channel, c)

    def test_channel_setter_invalid_raises(self):
        f = make_filter()
        with self.assertRaises(ValueError):
            f.channel = 3

    def test_channel_setter_negative_raises(self):
        f = make_filter()
        with self.assertRaises(ValueError):
            f.channel = -1

    def test_add_rgb_extracts_red(self):
        f = make_filter(channel=0)
        f.add(_RGB)
        np.testing.assert_array_equal(f.data, _RGB[:, :, 0])

    def test_add_rgb_extracts_green(self):
        f = make_filter(channel=1)
        f.add(_RGB)
        np.testing.assert_array_equal(f.data, _RGB[:, :, 1])

    def test_add_rgb_extracts_blue(self):
        f = make_filter(channel=2)
        f.add(_RGB)
        np.testing.assert_array_equal(f.data, _RGB[:, :, 2])

    def test_add_rgb_result_is_2d(self):
        f = make_filter(channel=0)
        f.add(_RGB)
        self.assertEqual(f.data.ndim, 2)

    def test_add_gray_stored_unchanged(self):
        f = make_filter()
        f.add(_GRAY)
        np.testing.assert_array_equal(f.data, _GRAY)

    def test_call_rgb_returns_channel(self):
        f = make_filter(channel=1)
        result = f(_RGB)
        np.testing.assert_array_equal(result, _RGB[:, :, 1])

    def test_call_gray_returns_unchanged(self):
        f = make_filter()
        result = f(_GRAY)
        np.testing.assert_array_equal(result, _GRAY)

    def test_data_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.data)


class TestQRGBFilter(unittest.TestCase):

    def test_is_qvideofilter(self):
        from QVideo.lib.QVideoFilter import QVideoFilter
        widget = make_widget()
        self.assertIsInstance(widget, QVideoFilter)

    def test_filter_is_rgb_filter(self):
        widget = make_widget()
        self.assertIsInstance(widget.filter, RGBFilter)

    def test_title(self):
        widget = make_widget()
        self.assertEqual(widget.title(), 'Color Channel')

    def test_initially_unchecked(self):
        widget = make_widget()
        self.assertFalse(widget.isChecked())

    def test_has_three_buttons(self):
        widget = make_widget()
        self.assertEqual(len(widget._buttons), 3)

    def test_default_button_checked(self):
        widget = make_widget()
        self.assertTrue(widget._buttons[0].isChecked())

    def test_set_channel_when_checked_updates_filter(self):
        widget = make_widget()
        widget.setChannel(True, 2)
        self.assertEqual(widget.filter.channel, 2)

    def test_set_channel_when_unchecked_does_not_update(self):
        widget = make_widget()
        widget.setChannel(True, 1)
        widget.setChannel(False, 1)
        self.assertEqual(widget.filter.channel, 1)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_RGB)
        np.testing.assert_array_equal(result, _RGB)

    def test_call_when_checked_applies_filter(self):
        widget = make_widget()
        widget.filter.channel = 1
        widget.setChecked(True)
        result = widget(_RGB)
        np.testing.assert_array_equal(result, _RGB[:, :, 1])


if __name__ == '__main__':
    unittest.main()
