'''Unit tests for CircleTransformFilter and QCircleTransformFilter.'''
import sys
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib.QVideoFilter import QVideoFilter, VideoFilter
from QVideo.filters.circletransform import (
    CircleTransformFilter, QCircleTransformFilter)


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_SHAPE = (32, 32)
_FRAME = np.random.randint(0, 256, _SHAPE, dtype=np.uint8)
_COLOR = np.random.randint(0, 256, (*_SHAPE, 3), dtype=np.uint8)


def make_filter(**kwargs) -> CircleTransformFilter:
    return CircleTransformFilter(**kwargs)


def make_widget() -> QCircleTransformFilter:
    return QCircleTransformFilter(parent=None)


class TestCircleTransformFilterInit(unittest.TestCase):

    def test_is_video_filter(self):
        self.assertIsInstance(CircleTransformFilter(), VideoFilter)

    def test_default_window(self):
        self.assertEqual(CircleTransformFilter().window, 13)

    def test_default_polyorder(self):
        self.assertEqual(CircleTransformFilter().polyorder, 3)

    def test_custom_window(self):
        self.assertEqual(CircleTransformFilter(window=7).window, 7)

    def test_custom_polyorder(self):
        self.assertEqual(CircleTransformFilter(polyorder=2).polyorder, 2)


class TestCircleTransformFilterDgimage(unittest.TestCase):

    def test_missing_dgimage_raises_actionable_error(self):
        with patch.dict(sys.modules, {'dgimage': None}):
            with self.assertRaisesRegex(ImportError,
                                        r'QVideo\[circletransform\]'):
                CircleTransformFilter()

    def test_importing_the_module_does_not_import_dgimage(self):
        import subprocess
        code = ('import sys; import QVideo.filters.circletransform; '
                'sys.exit(int("dgimage" in sys.modules))')
        result = subprocess.run([sys.executable, '-c', code],
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())


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


class TestCircleTransformFilterDeep(unittest.TestCase):

    def setUp(self):
        self.filter = make_filter(window=5)
        self.counts = (_FRAME.astype(np.uint16) * 16)   # 12 bit counts

    def test_it_is_deep(self):
        self.assertTrue(self.filter.deep)

    def test_a_deep_frame_gives_a_uint16_map(self):
        result = self.filter.process(self.counts)
        self.assertEqual(result.dtype, np.uint16)
        self.assertEqual(result.shape, _SHAPE)

    def test_the_peak_is_the_white_level(self):
        self.filter.levels = (0., 4095.)
        self.assertEqual(int(self.filter.process(self.counts).max()), 4095)

    def test_the_map_stays_between_the_levels(self):
        self.filter.levels = (100., 4095.)
        result = self.filter.process(self.counts)
        self.assertGreaterEqual(int(result.min()), 100)
        self.assertEqual(int(result.max()), 4095)

    def test_without_levels_the_whole_range_is_used(self):
        self.assertEqual(int(self.filter.process(self.counts).max()), 65535)

    def test_it_agrees_with_the_8_bit_map_up_to_the_scale(self):
        deep = self.filter.process(self.counts).astype(float) / 65535 * 255
        plain = self.filter.process(_FRAME).astype(float)
        np.testing.assert_allclose(deep, plain, atol=1.)

    def test_the_8_bit_map_is_as_before(self):
        self.assertEqual(self.filter.process(_FRAME).dtype, np.uint8)


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


def rings(shape, center, k=0.3):
    y, x = np.indices(shape)
    return np.round(127.5 * (1. + np.cos(
        k * np.hypot(x - center[0], y - center[1])))).astype(np.uint8)


class TestCircleTransformFilterFast(unittest.TestCase):

    '''The filter uses the fast options of dgimage by default.'''

    def test_the_defaults_are_single_precision_and_binning_2(self):
        f = CircleTransformFilter()
        self.assertEqual(f.binning, 2)
        self.assertEqual(f._transform.dtype, np.float32)

    def test_binning_may_be_changed_and_is_at_least_one(self):
        f = CircleTransformFilter(binning=4)
        self.assertEqual(f.binning, 4)
        f.binning = 0
        self.assertEqual(f.binning, 1)

    def test_the_map_has_the_shape_of_the_frame(self):
        for shape in ((96, 128), (95, 127), (97, 130)):
            for binning in (1, 2, 3):
                with self.subTest(shape=shape, binning=binning):
                    f = make_filter(window=5, binning=binning)
                    frame = rings(shape, (shape[1] // 2, shape[0] // 2))
                    self.assertEqual(f.process(frame).shape, shape)

    def test_the_peak_is_white(self):
        f = make_filter(window=5)
        self.assertEqual(int(f.process(rings((96, 128), (70, 40))).max()),
                         255)

    def test_a_sphere_is_found_where_it_is(self):
        for binning in (1, 2, 4):
            with self.subTest(binning=binning):
                f = make_filter(window=5, polyorder=2, binning=binning)
                # rings 40 pixels apart: binning averages away finer ones
                heat = f.process(rings((96, 128), (70, 40), k=0.15))
                y, x = np.unravel_index(heat.argmax(), heat.shape)
                self.assertLessEqual(abs(int(x) - 70), 3)
                self.assertLessEqual(abs(int(y) - 40), 3)

    def test_the_map_agrees_with_dgimage_without_binning(self):
        import dgimage
        frame = rings((96, 128), (70, 40))
        f = make_filter(window=5, binning=1)
        heat = dgimage.circletransform(frame, window=5)
        np.testing.assert_allclose(f.process(frame) / 255., heat, atol=0.01)

    def test_a_deep_frame_keeps_the_scale_with_binning(self):
        f = make_filter(window=5, binning=2)
        f.levels = (0., 4095.)
        counts = rings((96, 128), (70, 40)).astype(np.uint16) * 16
        result = f.process(counts)
        self.assertEqual(result.dtype, np.uint16)
        self.assertEqual(int(result.max()), 4095)
        self.assertEqual(result.shape, (96, 128))


class TestQCircleTransformFilterWidget(unittest.TestCase):

    def test_filter_is_circle_transform_filter(self):
        self.assertIsInstance(make_widget().videoFilter, CircleTransformFilter)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Circle Transform')

    def test_has_spinbox(self):
        w = make_widget()
        self.assertTrue(hasattr(w, '_spinbox'))

    def test_spinbox_default_value(self):
        w = make_widget()
        self.assertEqual(w._spinbox.value(), 13)

    def test_binning_spinbox_follows_the_filter(self):
        w = make_widget()
        self.assertEqual(w._binbox.value(), 2)
        w._binbox.setValue(4)
        self.assertEqual(w.videoFilter.binning, 4)
        w._binbox.setValue(1)
        self.assertEqual(w.videoFilter.binning, 1)

    def test_spinbox_minimum(self):
        w = make_widget()
        self.assertEqual(w._spinbox.opts['bounds'][0], 3)

    def test_set_window_updates_filter(self):
        w = make_widget()
        w._setWindow(9)
        self.assertEqual(w.videoFilter.window, 9)

    def test_set_window_rounds_to_odd(self):
        w = make_widget()
        w._setWindow(8)
        self.assertEqual(w.videoFilter.window, 9)

    def test_set_window_updates_spinbox(self):
        w = make_widget()
        w._setWindow(8)
        self.assertEqual(w._spinbox.value(), 9)

    def test_initially_unchecked(self):
        self.assertFalse(make_widget().isChecked())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
