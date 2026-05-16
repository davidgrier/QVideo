'''Tests for GammaFilter and QGammaFilter.'''
import unittest
import numpy as np
from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestGammaFilter(unittest.TestCase):

    def setUp(self):
        from QVideo.filters.gamma import GammaFilter
        self.f = GammaFilter()

    def test_default_gamma(self):
        self.assertAlmostEqual(self.f.gamma, 1.0)

    def test_gamma_clamps_to_minimum(self):
        self.f.gamma = 0.0
        self.assertAlmostEqual(self.f.gamma, 0.1)

    def test_gamma_setter_stores_value(self):
        self.f.gamma = 2.2
        self.assertAlmostEqual(self.f.gamma, 2.2)

    def test_lut_built_on_init(self):
        self.assertEqual(self.f._lut.shape, (256,))
        self.assertEqual(self.f._lut.dtype, np.uint8)

    def test_lut_rebuilt_on_gamma_change(self):
        lut_before = self.f._lut.copy()
        self.f.gamma = 2.0
        self.assertFalse(np.array_equal(self.f._lut, lut_before))

    def test_get_none_when_no_data(self):
        self.assertIsNone(self.f.get())

    def test_get_grayscale(self):
        frame = np.arange(256, dtype=np.uint8).reshape(16, 16)
        self.f.add(frame)
        result = self.f.get()
        self.assertEqual(result.shape, frame.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_get_color(self):
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        frame[:] = 128
        self.f.add(frame)
        result = self.f.get()
        self.assertEqual(result.shape, frame.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_identity_gamma(self):
        frame = np.arange(256, dtype=np.uint8).reshape(16, 16)
        self.f.gamma = 1.0
        self.f.add(frame)
        result = self.f.get()
        np.testing.assert_array_equal(result, frame)

    def test_gamma_darkens_at_gt_one(self):
        frame = np.full((4, 4), 128, dtype=np.uint8)
        self.f.gamma = 2.0
        self.f.add(frame)
        result = self.f.get()
        self.assertLess(int(result[0, 0]), 128)

    def test_gamma_brightens_at_lt_one(self):
        frame = np.full((4, 4), 128, dtype=np.uint8)
        self.f.gamma = 0.5
        self.f.add(frame)
        result = self.f.get()
        self.assertGreater(int(result[0, 0]), 128)

    def test_to_code_returns_filtercode(self):
        from QVideo.lib.QVideoFilter import FilterCode
        code = self.f.to_code()
        self.assertIsInstance(code, FilterCode)

    def test_to_code_imports(self):
        code = self.f.to_code()
        self.assertIn('import numpy as np', code.imports)

    def test_to_code_has_lines(self):
        code = self.f.to_code()
        self.assertTrue(len(code.lines) > 0)

    def test_to_code_has_comment(self):
        code = self.f.to_code()
        self.assertIn('gamma', code.comment)


class TestQGammaFilter(unittest.TestCase):

    def setUp(self):
        from QVideo.filters.gamma import QGammaFilter
        self.w = QGammaFilter()

    def test_display_name(self):
        from QVideo.filters.gamma import QGammaFilter
        self.assertEqual(QGammaFilter.display_name, 'Gamma Correction')

    def test_display_category(self):
        from QVideo.filters.gamma import QGammaFilter
        self.assertEqual(QGammaFilter.display_category, 'Preprocessing')

    def test_filter_instance(self):
        from QVideo.filters.gamma import GammaFilter
        self.assertIsInstance(self.w.filter, GammaFilter)

    def test_spinbox_exists(self):
        self.assertTrue(hasattr(self.w, '_gammaBox'))

    def test_spinbox_initial_value(self):
        self.assertAlmostEqual(self.w._gammaBox.value(), 1.0)

    def test_set_gamma_updates_filter(self):
        self.w._setGamma(2.0)
        self.assertAlmostEqual(self.w.filter.gamma, 2.0)


if __name__ == '__main__':
    unittest.main()
