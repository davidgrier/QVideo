'''Unit tests for VideoFilter and QVideoFilter.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtWidgets
from QVideo.lib.VideoFilter import VideoFilter, QVideoFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.arange(12, dtype=np.uint8).reshape(3, 4)
_OTHER = np.ones((3, 4), dtype=np.uint8) * 99


def make_filter() -> VideoFilter:
    return VideoFilter()


def make_widget(checked=False) -> QVideoFilter:
    widget = QVideoFilter('Test', None, make_filter())
    widget.setChecked(checked)
    return widget


class TestVideoFilter(unittest.TestCase):

    def test_data_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.data)

    def test_add_stores_data(self):
        f = make_filter()
        f.add(_FRAME)
        np.testing.assert_array_equal(f.data, _FRAME)

    def test_get_returns_stored_data(self):
        f = make_filter()
        f.add(_FRAME)
        np.testing.assert_array_equal(f.get(), _FRAME)

    def test_call_returns_same_data(self):
        f = make_filter()
        result = f(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)

    def test_call_chains_add_then_get(self):
        f = make_filter()
        f(_FRAME)
        np.testing.assert_array_equal(f.data, _FRAME)

    def test_call_updates_on_successive_frames(self):
        f = make_filter()
        f(_FRAME)
        result = f(_OTHER)
        np.testing.assert_array_equal(result, _OTHER)

    def test_subclass_can_override_add(self):
        class DoubleFilter(VideoFilter):
            def add(self, data):
                self.data = data * 2

        f = DoubleFilter()
        result = f(np.array([1, 2, 3], dtype=np.uint8))
        np.testing.assert_array_equal(result, [2, 4, 6])

    def test_subclass_can_override_get(self):
        class ZeroFilter(VideoFilter):
            def get(self):
                return np.zeros_like(self.data)

        f = ZeroFilter()
        result = f(_FRAME)
        np.testing.assert_array_equal(result, np.zeros_like(_FRAME))


class TestQVideoFilter(unittest.TestCase):

    def test_is_qgroupbox(self):
        widget = make_widget()
        self.assertIsInstance(widget, QtWidgets.QGroupBox)

    def test_initially_unchecked(self):
        widget = make_widget()
        self.assertFalse(widget.isChecked())

    def test_is_checkable(self):
        widget = make_widget()
        self.assertTrue(widget.isCheckable())

    def test_is_flat(self):
        widget = make_widget()
        self.assertTrue(widget.isFlat())

    def test_filter_stored(self):
        f = make_filter()
        widget = QVideoFilter('Test', None, f)
        self.assertIs(widget.filter, f)

    def test_call_when_unchecked_returns_image_unchanged(self):
        widget = make_widget(checked=False)
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)

    def test_call_when_checked_applies_filter(self):
        widget = make_widget(checked=True)
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)  # passthrough filter

    def test_call_when_checked_delegates_to_filter(self):
        class ConstantFilter(VideoFilter):
            def get(self):
                return _OTHER

        widget = QVideoFilter('Test', None, ConstantFilter())
        widget.setChecked(True)
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _OTHER)

    def test_call_when_unchecked_does_not_call_filter(self):
        called = []

        class TrackingFilter(VideoFilter):
            def add(self, data):
                called.append(data)
                super().add(data)

        widget = QVideoFilter('Test', None, TrackingFilter())
        widget.setChecked(False)
        widget(_FRAME)
        self.assertEqual(len(called), 0)

    def test_set_filter_replaces_filter(self):
        widget = make_widget()
        new_filter = make_filter()
        widget.setFilter(new_filter)
        self.assertIs(widget.filter, new_filter)

    def test_set_filter_takes_effect_on_call(self):
        class ConstantFilter(VideoFilter):
            def get(self):
                return _OTHER

        widget = make_widget(checked=True)
        widget.setFilter(ConstantFilter())
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _OTHER)

    def test_has_layout(self):
        widget = make_widget()
        self.assertIsInstance(widget.layout, QtWidgets.QHBoxLayout)

    def test_title_set(self):
        widget = QVideoFilter('My Filter', None, make_filter())
        self.assertEqual(widget.title(), 'My Filter')


if __name__ == '__main__':
    unittest.main()
