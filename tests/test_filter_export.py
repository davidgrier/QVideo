'''Unit tests for FilterCode, VideoFilter.to_code, and QFilterRack.exportPipeline.'''
import unittest
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib.QVideoFilter import (
    FilterCode, VideoFilter, QVideoFilter, renderPipeline)
from QVideo.lib.QFilterRack import QFilterRack
from QVideo.filters.threshold import ThresholdFilter
from QVideo.filters.edge import EdgeFilter
from QVideo.filters.roi import ROIFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


_racks = []


def make_rack() -> QFilterRack:
    '''A rack, whose pipeline is stopped when the module's tests end.'''
    rack = QFilterRack(parent=None)
    _racks.append(rack)
    return rack


def tearDownModule():
    for rack in _racks:
        rack.pipeline.stop()
    _racks.clear()


class TestFilterCode(unittest.TestCase):

    def test_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(FilterCode))

    def test_default_comment_is_empty(self):
        fc = FilterCode(imports=frozenset(), lines=[])
        self.assertEqual(fc.comment, '')

    def test_imports_may_be_any_collection_of_lines(self):
        fc = FilterCode({'import cv2'}, [])
        self.assertEqual(fc.imports, frozenset({'import cv2'}))
        self.assertIsInstance(fc.imports, frozenset)

    def test_fields_stored(self):
        fc = FilterCode(imports=frozenset({'import cv2'}), lines=['x = 1'], comment='test')
        self.assertIn('import cv2', fc.imports)
        self.assertEqual(fc.lines, ['x = 1'])
        self.assertEqual(fc.comment, 'test')


class TestVideoFilterToCodeDefault(unittest.TestCase):

    def test_base_class_returns_none(self):
        f = VideoFilter()
        self.assertIsNone(f.to_code())


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


class TestRenderPipeline(unittest.TestCase):

    def fragment(self, comment='', imports=(), lines=('image = image',)):
        return FilterCode(frozenset(imports), list(lines), comment)

    def test_an_empty_pipeline_returns_the_image(self):
        src = renderPipeline([], [])
        self.assertTrue(src.endswith(
            'def filter(image: np.ndarray) -> np.ndarray:\n'
            '    return image\n'))

    def test_the_numpy_import_is_always_present(self):
        self.assertIn('import numpy as np\n', renderPipeline([], []))

    def test_imports_are_merged_and_sorted(self):
        src = renderPipeline(
            [self.fragment(imports={'import cv2'}),
             self.fragment(imports={'import cv2', 'import math'})], [])
        lines = src.split('\n')
        self.assertEqual(lines.count('import cv2'), 1)
        self.assertLess(lines.index('import cv2'),
                        lines.index('import math'))

    def test_fragments_keep_their_order_and_comments(self):
        src = renderPipeline(
            [self.fragment('first', lines=['image = 1']),
             self.fragment('second', lines=['image = 2'])], [])
        self.assertLess(src.index('# first'), src.index('image = 1'))
        self.assertLess(src.index('image = 1'), src.index('# second'))
        self.assertLess(src.index('image = 2'), src.index('return image'))

    def test_skipped_filters_are_listed_in_a_comment(self):
        src = renderPipeline([], ['SampleHold'])
        self.assertIn('#   SampleHold', src)

    def test_the_result_compiles(self):
        compile(renderPipeline([self.fragment('x')], ['Y']), '<g>', 'exec')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
