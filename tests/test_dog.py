'''Tests for DoGFilter and QDoGFilter.'''
import unittest
import numpy as np
from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestDoGFilter(unittest.TestCase):

    def setUp(self):
        from QVideo.filters.dog import DoGFilter
        self.f = DoGFilter()

    def test_default_low_sigma(self):
        self.assertAlmostEqual(self.f.low_sigma, 1.0)

    def test_default_high_sigma(self):
        self.assertAlmostEqual(self.f.high_sigma, 3.0)

    def test_low_sigma_clamps_to_minimum(self):
        self.f.low_sigma = 0.0
        self.assertGreaterEqual(self.f.low_sigma, 0.1)

    def test_low_sigma_rejected_when_ge_high(self):
        original = self.f.low_sigma
        self.f.low_sigma = self.f.high_sigma
        self.assertAlmostEqual(self.f.low_sigma, original)

    def test_high_sigma_clamps_to_minimum(self):
        f = __import__('QVideo.filters.dog', fromlist=['DoGFilter']).DoGFilter(
            low_sigma=0.1, high_sigma=10.0)
        f.high_sigma = 0.0
        self.assertGreaterEqual(f.high_sigma, 0.2)

    def test_high_sigma_rejected_when_le_low(self):
        original = self.f.high_sigma
        self.f.high_sigma = self.f.low_sigma
        self.assertAlmostEqual(self.f.high_sigma, original)

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
        self.assertEqual(result.ndim, 2)
        self.assertEqual(result.dtype, np.uint8)

    def test_get_returns_absolute_values(self):
        frame = np.random.randint(0, 256, (32, 32), dtype=np.uint8)
        self.f.add(frame)
        result = self.f.get()
        self.assertTrue(np.all(result >= 0))

    def test_uniform_image_gives_zero(self):
        frame = np.full((32, 32), 100, dtype=np.uint8)
        self.f.add(frame)
        result = self.f.get()
        np.testing.assert_array_equal(result, 0)

    def test_to_code_returns_filtercode(self):
        from QVideo.lib.QVideoFilter import FilterCode
        code = self.f.to_code()
        self.assertIsInstance(code, FilterCode)

    def test_to_code_imports(self):
        code = self.f.to_code()
        self.assertIn('import cv2', code.imports)
        self.assertIn('import numpy as np', code.imports)

    def test_to_code_has_lines(self):
        code = self.f.to_code()
        self.assertTrue(len(code.lines) > 0)

    def test_to_code_has_comment(self):
        code = self.f.to_code()
        self.assertIn('DoG', code.comment)


class TestQDoGFilter(unittest.TestCase):

    def setUp(self):
        from QVideo.filters.dog import QDoGFilter
        self.w = QDoGFilter()

    def test_filter_instance(self):
        from QVideo.filters.dog import DoGFilter
        self.assertIsInstance(self.w.filter, DoGFilter)

    def test_low_spinbox_exists(self):
        self.assertTrue(hasattr(self.w, '_lowBox'))

    def test_high_spinbox_exists(self):
        self.assertTrue(hasattr(self.w, '_highBox'))

    def test_low_spinbox_initial_value(self):
        self.assertAlmostEqual(self.w._lowBox.value(), 1.0)

    def test_high_spinbox_initial_value(self):
        self.assertAlmostEqual(self.w._highBox.value(), 3.0)

    def test_set_low_sigma_updates_filter(self):
        self.w._setLowSigma(0.5)
        self.assertAlmostEqual(self.w.filter.low_sigma, 0.5)

    def test_set_high_sigma_updates_filter(self):
        self.w._setHighSigma(5.0)
        self.assertAlmostEqual(self.w.filter.high_sigma, 5.0)

    def test_snap_back_on_invalid_low(self):
        original = self.w.filter.low_sigma
        self.w._setLowSigma(self.w.filter.high_sigma + 1.0)
        self.assertAlmostEqual(self.w._lowBox.value(), original)

    def test_snap_back_on_invalid_high(self):
        original = self.w.filter.high_sigma
        self.w._setHighSigma(self.w.filter.low_sigma - 0.1)
        self.assertAlmostEqual(self.w._highBox.value(), original)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
