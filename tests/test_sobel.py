'''Unit tests for SobelFilter and QSobelFilter.'''
import unittest
import numpy as np
from unittest.mock import patch, call
import cv2
from qtpy import QtWidgets
from QVideo.filters.sobel import SobelFilter, QSobelFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_GRAY = np.zeros((8, 8), dtype=np.uint8)
_COLOR = np.zeros((8, 8, 3), dtype=np.uint8)
_EDGE = np.zeros((8, 8), dtype=np.uint8)


def make_filter(**kwargs) -> SobelFilter:
    return SobelFilter(**kwargs)


def make_widget() -> QSobelFilter:
    return QSobelFilter(parent=None)


class TestSobelFilterDirection(unittest.TestCase):

    def test_default_direction(self):
        self.assertEqual(make_filter().direction, 'Magnitude')

    def test_custom_direction(self):
        self.assertEqual(make_filter(direction='Horizontal').direction, 'Horizontal')

    def test_direction_setter_valid(self):
        f = make_filter()
        f.direction = 'Vertical'
        self.assertEqual(f.direction, 'Vertical')

    def test_direction_setter_invalid(self):
        with self.assertRaises(ValueError):
            make_filter(direction='Diagonal')

    def test_all_directions_accepted(self):
        for d in SobelFilter.DIRECTIONS:
            f = make_filter()
            f.direction = d
            self.assertEqual(f.direction, d)


class TestSobelFilterKsize(unittest.TestCase):

    def test_default_ksize(self):
        self.assertEqual(make_filter().ksize, 3)

    def test_custom_ksize(self):
        self.assertEqual(make_filter(ksize=5).ksize, 5)

    def test_ksize_enforces_odd(self):
        self.assertEqual(make_filter(ksize=4).ksize % 2, 1)

    def test_ksize_clamps_to_minimum(self):
        self.assertGreaterEqual(make_filter(ksize=0).ksize, 1)

    def test_ksize_clamps_to_maximum(self):
        self.assertLessEqual(make_filter(ksize=99).ksize, 7)

    def test_ksize_odd_preserved(self):
        self.assertEqual(make_filter(ksize=7).ksize, 7)


class TestSobelFilterGet(unittest.TestCase):

    def test_get_returns_none_before_add(self):
        self.assertIsNone(make_filter().get())

    def test_get_returns_ndarray(self):
        f = make_filter()
        f.add(_GRAY)
        self.assertIsInstance(f.get(), np.ndarray)

    def test_get_horizontal_calls_sobel_x(self):
        f = make_filter(direction='Horizontal', ksize=3)
        f.add(_GRAY)
        _CSA = np.zeros_like(_GRAY)
        with patch('cv2.Sobel', return_value=_EDGE) as mock_s, \
             patch('cv2.convertScaleAbs', return_value=_CSA):
            f.get()
        mock_s.assert_called_once_with(_GRAY, cv2.CV_32F, 1, 0, ksize=3)

    def test_get_vertical_calls_sobel_y(self):
        f = make_filter(direction='Vertical', ksize=3)
        f.add(_GRAY)
        _CSA = np.zeros_like(_GRAY)
        with patch('cv2.Sobel', return_value=_EDGE) as mock_s, \
             patch('cv2.convertScaleAbs', return_value=_CSA):
            f.get()
        mock_s.assert_called_once_with(_GRAY, cv2.CV_32F, 0, 1, ksize=3)

    def test_get_magnitude_calls_sobel_twice(self):
        f = make_filter(direction='Magnitude', ksize=3)
        f.add(_GRAY)
        with patch('cv2.Sobel', return_value=_EDGE.astype(np.float32)) as mock_s:
            f.get()
        self.assertEqual(mock_s.call_count, 2)

    def test_get_magnitude_output_is_uint8(self):
        f = make_filter(direction='Magnitude')
        f.add(_GRAY)
        result = f.get()
        self.assertEqual(result.dtype, np.uint8)

    def test_color_frame_converted_to_grayscale(self):
        f = make_filter()
        f.add(_COLOR)
        _CSA = np.zeros((_COLOR.shape[0], _COLOR.shape[1]), dtype=np.uint8)
        with patch('cv2.Sobel', return_value=_EDGE.astype(np.float32)) as mock_s:
            f.get()
        first_input = mock_s.call_args_list[0][0][0]
        self.assertEqual(first_input.ndim, 2)


class TestQSobelFilterInit(unittest.TestCase):

    def test_filter_is_sobel_filter(self):
        self.assertIsInstance(make_widget().filter, SobelFilter)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Sobel Edge Detection')


class TestQSobelFilterSetDirection(unittest.TestCase):

    def test_set_direction_updates_filter(self):
        w = make_widget()
        w._setDirection('Horizontal')
        self.assertEqual(w.filter.direction, 'Horizontal')

    def test_set_direction_vertical(self):
        w = make_widget()
        w._setDirection('Vertical')
        self.assertEqual(w.filter.direction, 'Vertical')


class TestQSobelFilterSetKsize(unittest.TestCase):

    def test_set_ksize_updates_filter(self):
        w = make_widget()
        w._setKsize(5)
        self.assertEqual(w.filter.ksize, 5)

    def test_set_ksize_snaps_spinbox_to_odd(self):
        w = make_widget()
        w._setKsize(4)
        self.assertEqual(w._ksizeBox.value() % 2, 1)


class TestQSobelFilterCall(unittest.TestCase):

    def test_call_unchecked_returns_frame_unchanged(self):
        w = make_widget()
        result = w(_GRAY)
        np.testing.assert_array_equal(result, _GRAY)

    def test_call_checked_applies_filter(self):
        w = make_widget()
        w.setChecked(True)
        with patch('cv2.Sobel', return_value=_EDGE.astype(np.float32)):
            result = w(_GRAY)
        self.assertIsInstance(result, np.ndarray)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
