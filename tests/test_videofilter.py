'''Unit tests for VideoFilter and QVideoFilter.'''
import unittest
import numpy as np
from qtpy import QtWidgets
from unittest.mock import patch
from qtpy import QtCore
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.arange(12, dtype=np.uint8).reshape(3, 4)
_OTHER = np.ones((3, 4), dtype=np.uint8) * 99


def make_filter() -> VideoFilter:
    return VideoFilter()


def make_widget(checked=False) -> QVideoFilter:
    widget = QVideoFilter(None, 'Test', make_filter())
    widget.setChecked(checked)
    return widget


class TestVideoFilter(unittest.TestCase):

    def test_data_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.data)

    def test_get_before_add_raises(self):
        f = make_filter()
        with self.assertRaises(RuntimeError):
            f.get()

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
        widget = QVideoFilter(None, 'Test', f)
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

        widget = QVideoFilter(None, 'Test', ConstantFilter())
        widget.setChecked(True)
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _OTHER)

    def test_call_when_unchecked_does_not_call_filter(self):
        called = []

        class TrackingFilter(VideoFilter):
            def add(self, data):
                called.append(data)
                super().add(data)

        widget = QVideoFilter(None, 'Test', TrackingFilter())
        widget.setChecked(False)
        widget(_FRAME)
        self.assertEqual(len(called), 0)

    def test_set_filter_replaces_filter(self):
        widget = make_widget()
        new_filter = make_filter()
        widget.filter = new_filter
        self.assertIs(widget.filter, new_filter)

    def test_set_filter_takes_effect_on_call(self):
        class ConstantFilter(VideoFilter):
            def get(self):
                return _OTHER

        widget = make_widget(checked=True)
        widget.filter = ConstantFilter()
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _OTHER)

    def test_filter_setter_rejects_non_filter(self):
        widget = make_widget()
        with self.assertRaises(TypeError):
            widget.filter = 'not a filter'

    def test_has_layout(self):
        widget = make_widget()
        self.assertIsInstance(widget._layout, QtWidgets.QHBoxLayout)

    def test_title_set(self):
        widget = QVideoFilter(None, 'My Filter', make_filter())
        self.assertEqual(widget.title(), 'My Filter')


class _FailingFilter(VideoFilter):
    '''Filter that raises every time it is called.'''

    def __init__(self):
        super().__init__()
        self.calls = 0

    def add(self, data):
        self.calls += 1
        raise ValueError('bad frame')


class _FailingAsyncFilter(AsyncVideoFilter):
    def process(self, image):
        raise ValueError('bad frame')


def make_failing_widget(videoFilter=None) -> QVideoFilter:
    widget = QVideoFilter(None, 'Test', videoFilter or _FailingFilter())
    widget.setChecked(True)
    return widget


class TestQVideoFilterSwitchOff(unittest.TestCase):

    def test_unchecks_the_widget(self):
        widget = make_widget(checked=True)
        widget.switchOff(ValueError('nope'))
        self.assertFalse(widget.isChecked())

    def test_tooltip_gives_the_reason(self):
        widget = make_widget(checked=True)
        widget.switchOff(ValueError('nope'))
        self.assertIn('nope', widget.toolTip())

    def test_tooltip_is_cleared_when_rechecked(self):
        widget = make_widget(checked=True)
        widget.switchOff(ValueError('nope'))
        widget.setChecked(True)
        self.assertEqual(widget.toolTip(), '')


class TestQVideoFilterFailure(unittest.TestCase):
    '''A filter that raises switches itself off and passes frames through.'''

    LOGGER = 'QVideo.lib.QVideoFilter'

    def _fail(self, widget):
        with self.assertLogs(self.LOGGER, level='ERROR') as cm:
            result = widget(_FRAME)
        return result, cm

    def test_failed_call_returns_the_image_unchanged(self):
        result, _ = self._fail(make_failing_widget())
        np.testing.assert_array_equal(result, _FRAME)

    def test_failed_filter_is_unchecked(self):
        widget = make_failing_widget()
        self._fail(widget)
        self.assertFalse(widget.isChecked())

    def test_failure_is_logged_once_with_the_filter_name(self):
        widget = make_failing_widget()
        _, cm = self._fail(widget)
        self.assertEqual(len(cm.records), 1)
        self.assertIn('_FailingFilter', cm.output[0])

    def test_disabled_filter_is_not_called_again(self):
        widget = make_failing_widget()
        self._fail(widget)
        widget(_FRAME)
        widget(_FRAME)
        self.assertEqual(widget.filter.calls, 1)

    def test_rechecking_retries_the_filter(self):
        widget = make_failing_widget()
        self._fail(widget)
        widget.setChecked(True)
        self._fail(widget)
        self.assertEqual(widget.filter.calls, 2)

    def test_tooltip_explains_the_failure(self):
        widget = make_failing_widget()
        self._fail(widget)
        self.assertIn('bad frame', widget.toolTip())

    def test_tooltip_is_cleared_when_rechecked(self):
        widget = make_failing_widget()
        self._fail(widget)
        widget.setChecked(True)
        self.assertEqual(widget.toolTip(), '')

    def test_failing_async_filter_is_also_disabled(self):
        with patch.object(QtCore.QThread, 'start'), \
             patch.object(QtCore.QObject, 'moveToThread'):
            widget = make_failing_widget(_FailingAsyncFilter())
        result, _ = self._fail(widget)
        np.testing.assert_array_equal(result, _FRAME)
        self.assertFalse(widget.isChecked())


if __name__ == '__main__':
    unittest.main()
