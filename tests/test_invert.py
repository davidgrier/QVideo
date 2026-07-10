'''Tests for InvertFilter and QInvertFilter.'''
import unittest
import numpy as np
from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestInvertFilter(unittest.TestCase):

    def setUp(self):
        from QVideo.filters.invert import InvertFilter
        self.f = InvertFilter()

    def test_get_none_when_no_data(self):
        self.assertIsNone(self.f.get())

    def test_get_grayscale_inverts(self):
        frame = np.arange(256, dtype=np.uint8).reshape(16, 16)
        self.f.add(frame)
        result = self.f.get()
        np.testing.assert_array_equal(result, 255 - frame)

    def test_get_color_inverts(self):
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        frame[:] = (10, 20, 30)
        self.f.add(frame)
        result = self.f.get()
        expected = np.zeros_like(frame)
        expected[:] = (245, 235, 225)
        np.testing.assert_array_equal(result, expected)

    def test_result_shape_and_dtype(self):
        frame = np.full((4, 4), 128, dtype=np.uint8)
        self.f.add(frame)
        result = self.f.get()
        self.assertEqual(result.shape, frame.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_double_inversion_is_identity(self):
        frame = np.arange(256, dtype=np.uint8).reshape(16, 16)
        self.f.add(frame)
        once = self.f.get()
        self.f.add(once)
        twice = self.f.get()
        np.testing.assert_array_equal(twice, frame)

    def test_black_becomes_white(self):
        frame = np.zeros((4, 4), dtype=np.uint8)
        self.f.add(frame)
        result = self.f.get()
        np.testing.assert_array_equal(result, np.full((4, 4), 255,
                                                        dtype=np.uint8))

    def test_to_code_returns_filtercode(self):
        from QVideo.lib.QVideoFilter import FilterCode
        code = self.f.to_code()
        self.assertIsInstance(code, FilterCode)

    def test_to_code_imports(self):
        code = self.f.to_code()
        self.assertIn('import cv2', code.imports)

    def test_to_code_has_lines(self):
        code = self.f.to_code()
        self.assertTrue(len(code.lines) > 0)

    def test_to_code_has_comment(self):
        code = self.f.to_code()
        self.assertIn('inversion', code.comment)


class TestQInvertFilter(unittest.TestCase):

    def setUp(self):
        from QVideo.filters.invert import QInvertFilter
        self.w = QInvertFilter()

    def test_filter_instance(self):
        from QVideo.filters.invert import InvertFilter
        self.assertIsInstance(self.w.filter, InvertFilter)

    def test_title(self):
        self.assertEqual(self.w.title(), 'Invert')

    def test_call_when_unchecked_returns_frame_unchanged(self):
        frame = np.arange(256, dtype=np.uint8).reshape(16, 16)
        result = self.w(frame)
        np.testing.assert_array_equal(result, frame)

    def test_call_when_checked_applies_filter(self):
        frame = np.arange(256, dtype=np.uint8).reshape(16, 16)
        self.w.setChecked(True)
        result = self.w(frame)
        np.testing.assert_array_equal(result, 255 - frame)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
