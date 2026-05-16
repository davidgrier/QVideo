'''Unit tests for FilterCode, VideoFilter.to_code, and QFilterRack.exportPipeline.'''
import unittest
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib.QVideoFilter import FilterCode, VideoFilter, QVideoFilter
from QVideo.lib.QFilterRack import QFilterRack
from QVideo.filters.smoothing import SmoothingFilter
from QVideo.filters.threshold import ThresholdFilter
from QVideo.filters.edge import EdgeFilter
from QVideo.filters.sobel import SobelFilter
from QVideo.filters.laplacian import LaplacianFilter
from QVideo.filters.roi import ROIFilter
from QVideo.filters.rgb import RGBFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_rack() -> QFilterRack:
    return QFilterRack(parent=None)


class TestFilterCode(unittest.TestCase):

    def test_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(FilterCode))

    def test_default_comment_is_empty(self):
        fc = FilterCode(imports=frozenset(), lines=[])
        self.assertEqual(fc.comment, '')

    def test_fields_stored(self):
        fc = FilterCode(imports=frozenset({'import cv2'}), lines=['x = 1'], comment='test')
        self.assertIn('import cv2', fc.imports)
        self.assertEqual(fc.lines, ['x = 1'])
        self.assertEqual(fc.comment, 'test')


class TestVideoFilterToCodeDefault(unittest.TestCase):

    def test_base_class_returns_none(self):
        f = VideoFilter()
        self.assertIsNone(f.to_code())


class TestSmoothingFilterToCode(unittest.TestCase):

    def _make(self, **kw):
        with patch.object(QtCore.QThread, 'start'), \
             patch.object(QtCore.QObject, 'moveToThread'):
            return SmoothingFilter(**kw)

    def test_returns_filter_code(self):
        self.assertIsInstance(self._make().to_code(), FilterCode)

    def test_gaussian_imports_cv2(self):
        self.assertIn('import cv2', self._make(method='gaussian').to_code().imports)

    def test_median_imports_cv2(self):
        self.assertIn('import cv2', self._make(method='median').to_code().imports)

    def test_gaussian_uses_gaussian_blur(self):
        code = self._make(method='gaussian', width=5).to_code()
        self.assertTrue(any('GaussianBlur' in ln for ln in code.lines))

    def test_median_uses_median_blur(self):
        code = self._make(method='median', width=7).to_code()
        self.assertTrue(any('medianBlur' in ln for ln in code.lines))

    def test_ksize_in_gaussian_code(self):
        code = self._make(method='gaussian', width=9).to_code()
        self.assertTrue(any('9' in ln for ln in code.lines))

    def test_ksize_in_median_code(self):
        code = self._make(method='median', width=7).to_code()
        self.assertTrue(any('7' in ln for ln in code.lines))


class TestThresholdFilterToCode(unittest.TestCase):

    def test_global_returns_filter_code(self):
        self.assertIsInstance(ThresholdFilter(method='Global').to_code(), FilterCode)

    def test_global_contains_threshold_call(self):
        code = ThresholdFilter(method='Global', threshold=100).to_code()
        self.assertTrue(any('cv2.threshold' in ln for ln in code.lines))

    def test_global_threshold_value_in_code(self):
        code = ThresholdFilter(method='Global', threshold=80).to_code()
        self.assertTrue(any('80' in ln for ln in code.lines))

    def test_otsu_uses_otsu_flag(self):
        code = ThresholdFilter(method='Otsu').to_code()
        self.assertTrue(any('THRESH_OTSU' in ln for ln in code.lines))

    def test_adaptive_mean_uses_mean_flag(self):
        code = ThresholdFilter(method='Adaptive Mean').to_code()
        self.assertTrue(any('ADAPTIVE_THRESH_MEAN_C' in ln for ln in code.lines))

    def test_adaptive_gaussian_uses_gaussian_flag(self):
        code = ThresholdFilter(method='Adaptive Gaussian').to_code()
        self.assertTrue(any('ADAPTIVE_THRESH_GAUSSIAN_C' in ln for ln in code.lines))

    def test_adaptive_block_size_in_code(self):
        code = ThresholdFilter(method='Adaptive Mean', block_size=15).to_code()
        self.assertTrue(any('15' in ln for ln in code.lines))

    def test_all_methods_include_grayscale_conversion(self):
        for method in ThresholdFilter.METHODS:
            code = ThresholdFilter(method=method).to_code()
            self.assertTrue(any('ndim' in ln for ln in code.lines),
                            f'missing grayscale check for method={method!r}')


class TestEdgeFilterToCode(unittest.TestCase):

    def test_returns_filter_code(self):
        self.assertIsInstance(EdgeFilter().to_code(), FilterCode)

    def test_imports_cv2(self):
        self.assertIn('import cv2', EdgeFilter().to_code().imports)

    def test_uses_canny(self):
        code = EdgeFilter(low=30, high=90).to_code()
        self.assertTrue(any('Canny' in ln for ln in code.lines))

    def test_threshold_values_in_code(self):
        code = EdgeFilter(low=30, high=90).to_code()
        joined = ' '.join(code.lines)
        self.assertIn('30', joined)
        self.assertIn('90', joined)

    def test_includes_grayscale_conversion(self):
        code = EdgeFilter().to_code()
        self.assertTrue(any('COLOR_RGB2GRAY' in ln for ln in code.lines))


class TestSobelFilterToCode(unittest.TestCase):

    def test_returns_filter_code(self):
        self.assertIsInstance(SobelFilter().to_code(), FilterCode)

    def test_horizontal_calls_sobel_x(self):
        code = SobelFilter(direction='Horizontal', ksize=3).to_code()
        self.assertTrue(any('1, 0' in ln for ln in code.lines))

    def test_vertical_calls_sobel_y(self):
        code = SobelFilter(direction='Vertical', ksize=3).to_code()
        self.assertTrue(any('0, 1' in ln for ln in code.lines))

    def test_magnitude_uses_hypot(self):
        code = SobelFilter(direction='Magnitude').to_code()
        self.assertTrue(any('hypot' in ln for ln in code.lines))

    def test_ksize_in_code(self):
        code = SobelFilter(ksize=5).to_code()
        self.assertTrue(any('ksize=5' in ln for ln in code.lines))

    def test_all_directions_include_grayscale(self):
        for d in SobelFilter.DIRECTIONS:
            code = SobelFilter(direction=d).to_code()
            self.assertTrue(any('ndim' in ln for ln in code.lines))


class TestLaplacianFilterToCode(unittest.TestCase):

    def test_returns_filter_code(self):
        self.assertIsInstance(LaplacianFilter().to_code(), FilterCode)

    def test_uses_laplacian(self):
        code = LaplacianFilter(ksize=3).to_code()
        self.assertTrue(any('Laplacian' in ln for ln in code.lines))

    def test_ksize_in_code(self):
        code = LaplacianFilter(ksize=5).to_code()
        self.assertTrue(any('ksize=5' in ln for ln in code.lines))

    def test_sigma_zero_skips_gaussian_blur(self):
        code = LaplacianFilter(sigma=0).to_code()
        self.assertFalse(any('GaussianBlur' in ln for ln in code.lines))

    def test_sigma_nonzero_includes_gaussian_blur(self):
        code = LaplacianFilter(sigma=1.5).to_code()
        self.assertTrue(any('GaussianBlur' in ln for ln in code.lines))

    def test_sigma_value_in_code(self):
        code = LaplacianFilter(sigma=2.0).to_code()
        self.assertTrue(any('2.0' in ln for ln in code.lines))

    def test_includes_grayscale_conversion(self):
        code = LaplacianFilter().to_code()
        self.assertTrue(any('ndim' in ln for ln in code.lines))


class TestROIFilterToCode(unittest.TestCase):

    def test_returns_filter_code(self):
        self.assertIsInstance(ROIFilter().to_code(), FilterCode)

    def test_slice_in_code(self):
        code = ROIFilter(x=10, y=20, w=100, h=80).to_code()
        self.assertEqual(len(code.lines), 1)
        self.assertIn('[20:100, 10:110]', code.lines[0])

    def test_no_imports_needed(self):
        self.assertEqual(ROIFilter().to_code().imports, frozenset())


class TestRGBFilterToCode(unittest.TestCase):

    def test_returns_filter_code(self):
        self.assertIsInstance(RGBFilter().to_code(), FilterCode)

    def test_red_channel_index(self):
        code = RGBFilter(channel=0).to_code()
        self.assertIn(':, :, 0', code.lines[0])

    def test_green_channel_index(self):
        code = RGBFilter(channel=1).to_code()
        self.assertIn(':, :, 1', code.lines[0])

    def test_blue_channel_index(self):
        code = RGBFilter(channel=2).to_code()
        self.assertIn(':, :, 2', code.lines[0])

    def test_no_imports_needed(self):
        self.assertEqual(RGBFilter().to_code().imports, frozenset())


class TestExportPipeline(unittest.TestCase):

    def test_empty_rack_has_function_def(self):
        src = make_rack().exportPipeline()
        self.assertIn('def filter(image', src)

    def test_empty_rack_returns_image(self):
        src = make_rack().exportPipeline()
        self.assertIn('return image', src)

    def test_always_imports_numpy(self):
        src = make_rack().exportPipeline()
        self.assertIn('import numpy as np', src)

    def test_includes_module_docstring(self):
        src = make_rack().exportPipeline()
        self.assertIn('QVideo', src)

    def test_skips_unchecked_filter(self):
        rack = make_rack()
        w = QVideoFilter(None, 'Edge', EdgeFilter())
        w.setChecked(False)
        rack.add(w)
        src = rack.exportPipeline()
        self.assertNotIn('Canny', src)

    def test_includes_checked_filter(self):
        rack = make_rack()
        w = QVideoFilter(None, 'Edge', EdgeFilter())
        w.setChecked(True)
        rack.add(w)
        src = rack.exportPipeline()
        self.assertIn('Canny', src)

    def test_filter_with_no_to_code_omitted_with_note(self):
        rack = make_rack()
        w = QVideoFilter(None, 'Base', VideoFilter())
        w.setChecked(True)
        rack.add(w)
        src = rack.exportPipeline()
        self.assertIn('NOTE', src)
        self.assertIn('VideoFilter', src)

    def test_multiple_filters_ordered(self):
        rack = make_rack()
        w1 = QVideoFilter(None, 'ROI', ROIFilter(x=0, y=0, w=64, h=64))
        w1.setChecked(True)
        w2 = QVideoFilter(None, 'Edge', EdgeFilter())
        w2.setChecked(True)
        rack.add(w1)
        rack.add(w2)
        src = rack.exportPipeline()
        self.assertLess(src.index('ROI'), src.index('Canny'))

    def test_generated_source_is_valid_python(self):
        rack = make_rack()
        w = QVideoFilter(None, 'Edge', EdgeFilter())
        w.setChecked(True)
        rack.add(w)
        src = rack.exportPipeline()
        compile(src, '<generated>', 'exec')

    def test_generated_source_with_threshold_is_valid_python(self):
        rack = make_rack()
        w = QVideoFilter(None, 'Threshold', ThresholdFilter(method='Otsu'))
        w.setChecked(True)
        rack.add(w)
        src = rack.exportPipeline()
        compile(src, '<generated>', 'exec')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
