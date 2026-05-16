'''Unit tests for LaplacianFilter and QLaplacianFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
import cv2
from qtpy import QtWidgets
from QVideo.filters.laplacian import LaplacianFilter, QLaplacianFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_GRAY = np.zeros((8, 8), dtype=np.uint8)
_COLOR = np.zeros((8, 8, 3), dtype=np.uint8)
_EDGE = np.zeros((8, 8), dtype=np.float32)


def make_filter(**kwargs) -> LaplacianFilter:
    return LaplacianFilter(**kwargs)


def make_widget() -> QLaplacianFilter:
    return QLaplacianFilter(parent=None)


class TestLaplacianFilterKsize(unittest.TestCase):

    def test_default_ksize(self):
        self.assertEqual(make_filter().ksize, 3)

    def test_custom_ksize(self):
        self.assertEqual(make_filter(ksize=5).ksize, 5)

    def test_ksize_enforces_odd(self):
        self.assertEqual(make_filter(ksize=4).ksize % 2, 1)

    def test_ksize_enforces_minimum(self):
        self.assertGreaterEqual(make_filter(ksize=0).ksize, 1)

    def test_ksize_odd_preserved(self):
        self.assertEqual(make_filter(ksize=7).ksize, 7)


class TestLaplacianFilterSigma(unittest.TestCase):

    def test_default_sigma(self):
        self.assertEqual(make_filter().sigma, 0.0)

    def test_custom_sigma(self):
        self.assertAlmostEqual(make_filter(sigma=1.5).sigma, 1.5)

    def test_sigma_clamped_to_zero(self):
        self.assertEqual(make_filter(sigma=-1.0).sigma, 0.0)

    def test_sigma_setter(self):
        f = make_filter()
        f.sigma = 2.0
        self.assertAlmostEqual(f.sigma, 2.0)


class TestLaplacianFilterGet(unittest.TestCase):

    def test_get_returns_none_before_add(self):
        self.assertIsNone(make_filter().get())

    def test_get_returns_ndarray(self):
        f = make_filter()
        f.add(_GRAY)
        self.assertIsInstance(f.get(), np.ndarray)

    def test_get_calls_cv2_laplacian(self):
        f = make_filter(ksize=3)
        f.add(_GRAY)
        with patch('cv2.Laplacian', return_value=_EDGE) as mock_l, \
             patch('cv2.convertScaleAbs', return_value=np.zeros_like(_GRAY)):
            f.get()
        mock_l.assert_called_once_with(_GRAY, cv2.CV_32F, ksize=3)

    def test_get_with_sigma_calls_gaussian_blur_first(self):
        f = make_filter(ksize=3, sigma=1.0)
        f.add(_GRAY)
        blurred = np.zeros_like(_GRAY)
        with patch('cv2.GaussianBlur', return_value=blurred) as mock_blur, \
             patch('cv2.Laplacian', return_value=_EDGE) as mock_lap, \
             patch('cv2.convertScaleAbs', return_value=np.zeros_like(_GRAY)):
            f.get()
        mock_blur.assert_called_once_with(_GRAY, (0, 0), 1.0)
        lap_input = mock_lap.call_args[0][0]
        np.testing.assert_array_equal(lap_input, blurred)

    def test_get_without_sigma_skips_gaussian_blur(self):
        f = make_filter(ksize=3, sigma=0.0)
        f.add(_GRAY)
        with patch('cv2.GaussianBlur') as mock_blur, \
             patch('cv2.Laplacian', return_value=_EDGE), \
             patch('cv2.convertScaleAbs', return_value=np.zeros_like(_GRAY)):
            f.get()
        mock_blur.assert_not_called()

    def test_get_output_is_uint8(self):
        f = make_filter()
        f.add(_GRAY)
        result = f.get()
        self.assertEqual(result.dtype, np.uint8)

    def test_color_frame_converted_to_grayscale(self):
        f = make_filter()
        f.add(_COLOR)
        with patch('cv2.Laplacian', return_value=_EDGE) as mock_l, \
             patch('cv2.convertScaleAbs', return_value=np.zeros((_COLOR.shape[0], _COLOR.shape[1]), dtype=np.uint8)):
            f.get()
        lap_input = mock_l.call_args[0][0]
        self.assertEqual(lap_input.ndim, 2)


class TestQLaplacianFilterInit(unittest.TestCase):

    def test_is_qvideofilter(self):
        from QVideo.lib.QVideoFilter import QVideoFilter
        self.assertIsInstance(make_widget(), QVideoFilter)

    def test_filter_is_laplacian_filter(self):
        self.assertIsInstance(make_widget().filter, LaplacianFilter)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Laplacian Edge Detection')

    def test_display_name(self):
        self.assertEqual(QLaplacianFilter.display_name, 'Laplacian')

    def test_display_category(self):
        self.assertEqual(QLaplacianFilter.display_category, 'Edge Detection')

    def test_initially_unchecked(self):
        self.assertFalse(make_widget().isChecked())


class TestQLaplacianFilterSetKsize(unittest.TestCase):

    def test_set_ksize_updates_filter(self):
        w = make_widget()
        w._setKsize(5)
        self.assertEqual(w.filter.ksize, 5)

    def test_set_ksize_snaps_spinbox_to_odd(self):
        w = make_widget()
        w._setKsize(4)
        self.assertEqual(w._ksizeBox.value() % 2, 1)


class TestQLaplacianFilterSetSigma(unittest.TestCase):

    def test_set_sigma_updates_filter(self):
        w = make_widget()
        w._setSigma(1.5)
        self.assertAlmostEqual(w.filter.sigma, 1.5)

    def test_set_sigma_zero(self):
        w = make_widget()
        w._setSigma(0.0)
        self.assertEqual(w.filter.sigma, 0.0)


class TestQLaplacianFilterCall(unittest.TestCase):

    def test_call_unchecked_returns_frame_unchanged(self):
        w = make_widget()
        result = w(_GRAY)
        np.testing.assert_array_equal(result, _GRAY)

    def test_call_checked_applies_filter(self):
        w = make_widget()
        w.setChecked(True)
        with patch('cv2.Laplacian', return_value=_EDGE), \
             patch('cv2.convertScaleAbs', return_value=np.zeros_like(_GRAY)) as mock_csa:
            result = w(_GRAY)
        self.assertIsInstance(result, np.ndarray)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
