'''Unit tests for DarkFrameFilter and QDarkFrameFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox
from QVideo.tests.signals import record
from QVideo.filters.darkframe import DarkFrameFilter, QDarkFrameFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_SHAPE = (4, 4)
_DARK = np.full(_SHAPE, 20, dtype=np.uint8)
_BRIGHT = np.full(_SHAPE, 100, dtype=np.uint8)


def make_filter(**kwargs) -> DarkFrameFilter:
    return DarkFrameFilter(**kwargs)


def make_widget() -> QDarkFrameFilter:
    return QDarkFrameFilter(parent=None)


def _capture(f: DarkFrameFilter, frame: np.ndarray) -> None:
    '''Drive a complete capture cycle on f using frame.'''
    f.capture()
    for _ in range(f.nFrames):
        f.add(frame)


class TestDarkFrameFilterCapture(unittest.TestCase):

    def test_dark_stored_after_capture(self):
        f = make_filter(nFrames=4)
        _capture(f, _DARK)
        self.assertIsNotNone(f.reference)

    def test_dark_is_mean_of_frames(self):
        f = make_filter(nFrames=4)
        _capture(f, _DARK)
        np.testing.assert_array_equal(f.reference, _DARK)

    def test_dark_is_mean_of_mixed_frames(self):
        f = make_filter(nFrames=2)
        f.capture()
        a = np.full(_SHAPE, 10, dtype=np.uint8)
        b = np.full(_SHAPE, 30, dtype=np.uint8)
        f.add(a)
        f.add(b)
        np.testing.assert_array_equal(f.reference, np.full(_SHAPE, 20, dtype=np.uint8))


class TestDarkFrameFilterGet(unittest.TestCase):

    def test_get_with_dark_subtracts(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        f.add(_BRIGHT)
        expected = np.full(_SHAPE, 80, dtype=np.uint8)
        np.testing.assert_array_equal(f.get(), expected)

    def test_get_clips_to_zero(self):
        bright_dark = np.full(_SHAPE, 150, dtype=np.uint8)
        f = make_filter(nFrames=1)
        _capture(f, bright_dark)
        f.add(_DARK)
        np.testing.assert_array_equal(f.get(), np.zeros(_SHAPE, dtype=np.uint8))

    def test_get_preserves_dtype(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        f.add(_BRIGHT)
        self.assertEqual(f.get().dtype, np.uint8)


class TestQDarkFrameFilterInit(unittest.TestCase):

    def test_filter_is_dark_frame_filter(self):
        self.assertIsInstance(make_widget().filter, DarkFrameFilter)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Dark Frame')

    def test_display_name(self):
        self.assertEqual(QDarkFrameFilter.display_name, 'Dark Frame')

    def test_display_category(self):
        self.assertEqual(QDarkFrameFilter.display_category, 'Calibration')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
