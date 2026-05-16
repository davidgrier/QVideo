'''Tests for UnsharpFilter and QUnsharpFilter.'''
import unittest
import numpy as np
from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestUnsharpFilter(unittest.TestCase):

    def setUp(self):
        from QVideo.filters.unsharp import UnsharpFilter
        self.f = UnsharpFilter()

    def test_default_radius(self):
        self.assertAlmostEqual(self.f.radius, 2.0)

    def test_default_amount(self):
        self.assertAlmostEqual(self.f.amount, 1.0)

    def test_radius_clamps_to_minimum(self):
        self.f.radius = 0.0
        self.assertGreaterEqual(self.f.radius, 0.1)

    def test_amount_clamps_to_minimum(self):
        self.f.amount = -1.0
        self.assertGreaterEqual(self.f.amount, 0.0)

    def test_radius_setter_stores_value(self):
        self.f.radius = 3.5
        self.assertAlmostEqual(self.f.radius, 3.5)

    def test_amount_setter_stores_value(self):
        self.f.amount = 2.0
        self.assertAlmostEqual(self.f.amount, 2.0)

    def test_get_none_when_no_data(self):
        self.assertIsNone(self.f.get())

    def test_get_grayscale(self):
        frame = np.random.randint(0, 256, (32, 32), dtype=np.uint8)
        self.f.add(frame)
        result = self.f.get()
        self.assertEqual(result.shape, frame.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_get_color(self):
        frame = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
        self.f.add(frame)
        result = self.f.get()
        self.assertEqual(result.shape, frame.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_zero_amount_is_passthrough(self):
        frame = np.random.randint(0, 256, (32, 32), dtype=np.uint8)
        self.f.amount = 0.0
        self.f.add(frame)
        result = self.f.get()
        np.testing.assert_array_equal(result, frame)

    def test_sharpening_increases_edge_contrast(self):
        frame = np.zeros((32, 32), dtype=np.uint8)
        frame[:, 16:] = 200
        self.f.amount = 2.0
        self.f.add(frame)
        result = self.f.get()
        edge_contrast_before = abs(int(frame[16, 16]) - int(frame[16, 15]))
        edge_contrast_after = abs(int(result[16, 16]) - int(result[16, 15]))
        self.assertGreaterEqual(edge_contrast_after, edge_contrast_before)

    def test_to_code_returns_filtercode(self):
        from QVideo.lib.QVideoFilter import FilterCode
        code = self.f.to_code()
        self.assertIsInstance(code, FilterCode)

    def test_to_code_imports(self):
        code = self.f.to_code()
        self.assertIn('import cv2', code.imports)

    def test_to_code_has_lines(self):
        code = self.f.to_code()
        self.assertTrue(len(code.lines) >= 2)

    def test_to_code_has_comment(self):
        code = self.f.to_code()
        self.assertIn('unsharp', code.comment)

    def test_to_code_references_addweighted(self):
        code = self.f.to_code()
        joined = ' '.join(code.lines)
        self.assertIn('addWeighted', joined)


class TestQUnsharpFilter(unittest.TestCase):

    def setUp(self):
        from QVideo.filters.unsharp import QUnsharpFilter
        self.w = QUnsharpFilter()

    def test_display_name(self):
        from QVideo.filters.unsharp import QUnsharpFilter
        self.assertEqual(QUnsharpFilter.display_name, 'Unsharp Mask')

    def test_display_category(self):
        from QVideo.filters.unsharp import QUnsharpFilter
        self.assertEqual(QUnsharpFilter.display_category, 'Preprocessing')

    def test_filter_instance(self):
        from QVideo.filters.unsharp import UnsharpFilter
        self.assertIsInstance(self.w.filter, UnsharpFilter)

    def test_radius_spinbox_exists(self):
        self.assertTrue(hasattr(self.w, '_radiusBox'))

    def test_amount_spinbox_exists(self):
        self.assertTrue(hasattr(self.w, '_amountBox'))

    def test_radius_spinbox_initial_value(self):
        self.assertAlmostEqual(self.w._radiusBox.value(), 2.0)

    def test_amount_spinbox_initial_value(self):
        self.assertAlmostEqual(self.w._amountBox.value(), 1.0)

    def test_set_radius_updates_filter(self):
        self.w._setRadius(5.0)
        self.assertAlmostEqual(self.w.filter.radius, 5.0)

    def test_set_amount_updates_filter(self):
        self.w._setAmount(0.5)
        self.assertAlmostEqual(self.w.filter.amount, 0.5)


if __name__ == '__main__':
    unittest.main()
