'''Unit tests for CircleTransformFilter and QCircleTransformFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.filters.circletransform import (
    CircleTransformFilter, QCircleTransformFilter)


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_SHAPE = (32, 32)
_FRAME = np.random.randint(0, 256, _SHAPE, dtype=np.uint8)
_COLOR = np.random.randint(0, 256, (*_SHAPE, 3), dtype=np.uint8)


def make_filter(**kwargs) -> CircleTransformFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return CircleTransformFilter(**kwargs)


def make_widget() -> QCircleTransformFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return QCircleTransformFilter(parent=None)


class TestCircleTransformFilterInit(unittest.TestCase):

    def setUp(self):
        self._p_start = patch.object(QtCore.QThread, 'start')
        self._p_move = patch.object(QtCore.QObject, 'moveToThread')
        self._p_start.start()
        self._p_move.start()

    def tearDown(self):
        self._p_start.stop()
        self._p_move.stop()

    def test_is_async_video_filter(self):
        self.assertIsInstance(CircleTransformFilter(), AsyncVideoFilter)

    def test_default_window(self):
        self.assertEqual(CircleTransformFilter().window, 13)

    def test_default_polyorder(self):
        self.assertEqual(CircleTransformFilter().polyorder, 3)

    def test_custom_window(self):
        self.assertEqual(CircleTransformFilter(window=7).window, 7)

    def test_custom_polyorder(self):
        self.assertEqual(CircleTransformFilter(polyorder=2).polyorder, 2)


class TestCircleTransformFilterWindow(unittest.TestCase):

    def test_window_rounds_even_up_to_odd(self):
        f = make_filter(window=4)
        self.assertEqual(f.window, 5)

    def test_window_leaves_odd_unchanged(self):
        f = make_filter(window=7)
        self.assertEqual(f.window, 7)

    def test_window_minimum_is_3(self):
        f = make_filter(window=1)
        self.assertEqual(f.window, 3)

    def test_window_setter(self):
        f = make_filter()
        f.window = 9
        self.assertEqual(f.window, 9)

    def test_polyorder_minimum_is_1(self):
        f = make_filter(polyorder=0)
        self.assertEqual(f.polyorder, 1)


class TestCircleTransformFilterProcess(unittest.TestCase):

    def test_grayscale_returns_uint8(self):
        f = make_filter(window=5)
        result = f.process(_FRAME)
        self.assertEqual(result.dtype, np.uint8)

    def test_grayscale_output_shape_matches_input(self):
        f = make_filter(window=5)
        result = f.process(_FRAME)
        self.assertEqual(result.shape, _SHAPE)

    def test_color_returns_uint8(self):
        f = make_filter(window=5)
        result = f.process(_COLOR)
        self.assertEqual(result.dtype, np.uint8)

    def test_color_output_shape_is_2d(self):
        f = make_filter(window=5)
        result = f.process(_COLOR)
        self.assertEqual(result.shape, _SHAPE)

    def test_uniform_input_returns_zeros(self):
        f = make_filter(window=5)
        uniform = np.full(_SHAPE, 128, dtype=np.uint8)
        result = f.process(uniform)
        np.testing.assert_array_equal(result, np.zeros(_SHAPE, dtype=np.uint8))

    def test_output_values_in_uint8_range(self):
        f = make_filter(window=5)
        result = f.process(_FRAME)
        self.assertGreaterEqual(int(result.min()), 0)
        self.assertLessEqual(int(result.max()), 255)

    def test_nonuniform_input_saturates_to_255(self):
        f = make_filter(window=5)
        result = f.process(_FRAME)
        self.assertEqual(int(result.max()), 255)


class TestCircleTransformFilterKernel(unittest.TestCase):

    def test_process_consistent_for_same_shape(self):
        f = make_filter(window=5)
        r1 = f.process(_FRAME)
        r2 = f.process(_FRAME)
        np.testing.assert_array_equal(r1, r2)

    def test_process_handles_shape_change(self):
        f = make_filter(window=5)
        small = np.random.randint(0, 256, (16, 16), dtype=np.uint8)
        r1 = f.process(small)
        r2 = f.process(_FRAME)
        self.assertEqual(r1.shape, (16, 16))
        self.assertEqual(r2.shape, _SHAPE)

    def test_kernel_shape_matches_requested(self):
        f = make_filter()
        k = f._kernel_for(_SHAPE)
        self.assertEqual(k.shape, _SHAPE)


class TestQCircleTransformFilterWidget(unittest.TestCase):

    def test_filter_is_circle_transform_filter(self):
        self.assertIsInstance(make_widget().filter, CircleTransformFilter)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Circle Transform')

    def test_has_spinbox(self):
        w = make_widget()
        self.assertTrue(hasattr(w, '_spinbox'))

    def test_spinbox_default_value(self):
        w = make_widget()
        self.assertEqual(w._spinbox.value(), 13)

    def test_spinbox_minimum(self):
        w = make_widget()
        self.assertEqual(w._spinbox.opts['bounds'][0], 3)

    def test_set_window_updates_filter(self):
        w = make_widget()
        w._setWindow(9)
        self.assertEqual(w.filter.window, 9)

    def test_set_window_rounds_to_odd(self):
        w = make_widget()
        w._setWindow(8)
        self.assertEqual(w.filter.window, 9)

    def test_set_window_updates_spinbox(self):
        w = make_widget()
        w._setWindow(8)
        self.assertEqual(w._spinbox.value(), 9)

    def test_initially_unchecked(self):
        self.assertFalse(make_widget().isChecked())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
