'''Unit tests for FlatFieldFilter and QFlatFieldFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.tests.signals import record
from QVideo.filters.flatfield import FlatFieldFilter, QFlatFieldFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_SHAPE = (4, 4)
_UNIFORM = np.full(_SHAPE, 100, dtype=np.uint8)
_BRIGHT = np.full(_SHAPE, 200, dtype=np.uint8)


def make_filter(**kwargs) -> FlatFieldFilter:
    return FlatFieldFilter(**kwargs)


def make_widget() -> QFlatFieldFilter:
    return QFlatFieldFilter(parent=None)


def _capture(f: FlatFieldFilter, frame: np.ndarray) -> None:
    '''Drive a complete capture cycle on f using frame.'''
    f.capture()
    for _ in range(f.nFrames):
        f.add(frame)


class TestFlatFieldFilterCapture(unittest.TestCase):

    def test_flat_stored_after_capture(self):
        f = make_filter(nFrames=4)
        _capture(f, _UNIFORM)
        self.assertIsNotNone(f.reference)

    def test_flat_is_normalized_to_unit_mean(self):
        f = make_filter(nFrames=4)
        _capture(f, _UNIFORM)
        self.assertAlmostEqual(float(f.reference.mean()), 1.0, places=5)

    def test_flat_uniform_frame_is_all_ones(self):
        f = make_filter(nFrames=2)
        _capture(f, _UNIFORM)
        np.testing.assert_array_almost_equal(
            f.reference, np.ones(_SHAPE, dtype=np.float32))

    def test_flat_zero_mean_stores_none(self):
        f = make_filter(nFrames=1)
        _capture(f, np.zeros(_SHAPE, dtype=np.uint8))
        self.assertIsNone(f.reference)


class TestFlatFieldFilterGet(unittest.TestCase):

    def test_uniform_flat_is_identity(self):
        f = make_filter(nFrames=1)
        _capture(f, _UNIFORM)
        f.add(_BRIGHT)
        np.testing.assert_array_equal(f.get(), _BRIGHT)

    def test_bright_pixel_in_flat_dims_output(self):
        flat = _UNIFORM.copy()
        flat[0, 0] = 200
        f = make_filter(nFrames=1)
        _capture(f, flat)
        f.add(_UNIFORM)
        result = f.get()
        self.assertLess(int(result[0, 0]), int(result[1, 1]))

    def test_dark_pixel_in_flat_brightens_output(self):
        flat = _UNIFORM.copy()
        flat[0, 0] = 50
        f = make_filter(nFrames=1)
        _capture(f, flat)
        f.add(_UNIFORM)
        result = f.get()
        self.assertGreater(int(result[0, 0]), int(result[1, 1]))

    def test_zero_flat_pixel_passes_through(self):
        flat = _UNIFORM.copy()
        flat[0, 0] = 0
        f = make_filter(nFrames=1)
        _capture(f, flat)
        frame = np.full(_SHAPE, 80, dtype=np.uint8)
        f.add(frame)
        self.assertEqual(int(f.get()[0, 0]), 80)

    def test_get_clips_to_255(self):
        flat = np.full(_SHAPE, 50, dtype=np.uint8)
        f = make_filter(nFrames=1)
        _capture(f, flat)
        f.add(_BRIGHT)
        self.assertLessEqual(int(f.get().max()), 255)

    def test_get_preserves_dtype(self):
        f = make_filter(nFrames=1)
        _capture(f, _UNIFORM)
        f.add(_BRIGHT)
        self.assertEqual(f.get().dtype, np.uint8)


class TestQFlatFieldFilterInit(unittest.TestCase):

    def test_filter_is_flat_field_filter(self):
        self.assertIsInstance(make_widget().filter, FlatFieldFilter)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Flat Field')

    def test_display_name(self):
        self.assertEqual(QFlatFieldFilter.display_name, 'Flat Field')

    def test_display_category(self):
        self.assertEqual(
            QFlatFieldFilter.display_category, 'Calibration')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
