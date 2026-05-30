'''Unit tests for DarkFrameFilter and QDarkFrameFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtTest, QtWidgets
from pyqtgraph import SpinBox
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


class TestDarkFrameFilterInit(unittest.TestCase):

    def test_default_nFrames(self):
        self.assertEqual(make_filter().nFrames, 16)

    def test_custom_nFrames(self):
        self.assertEqual(make_filter(nFrames=8).nFrames, 8)

    def test_nFrames_minimum_is_1(self):
        self.assertEqual(make_filter(nFrames=0).nFrames, 1)

    def test_not_capturing_on_init(self):
        self.assertFalse(make_filter().isCapturing)

    def test_dark_none_on_init(self):
        self.assertIsNone(make_filter()._dark)

    def test_data_none_on_init(self):
        self.assertIsNone(make_filter().data)


class TestDarkFrameFilterCapture(unittest.TestCase):

    def test_capture_starts_counting(self):
        f = make_filter(nFrames=4)
        f.capture()
        self.assertTrue(f.isCapturing)

    def test_add_decrements_count(self):
        f = make_filter(nFrames=4)
        f.capture()
        f.add(_DARK)
        self.assertEqual(f._captureCount, 3)

    def test_capture_completes_after_nFrames(self):
        f = make_filter(nFrames=4)
        _capture(f, _DARK)
        self.assertFalse(f.isCapturing)

    def test_dark_stored_after_capture(self):
        f = make_filter(nFrames=4)
        _capture(f, _DARK)
        self.assertIsNotNone(f._dark)

    def test_dark_is_mean_of_frames(self):
        f = make_filter(nFrames=4)
        _capture(f, _DARK)
        np.testing.assert_array_equal(f._dark, _DARK)

    def test_dark_is_mean_of_mixed_frames(self):
        f = make_filter(nFrames=2)
        f.capture()
        a = np.full(_SHAPE, 10, dtype=np.uint8)
        b = np.full(_SHAPE, 30, dtype=np.uint8)
        f.add(a)
        f.add(b)
        np.testing.assert_array_equal(f._dark, np.full(_SHAPE, 20, dtype=np.uint8))

    def test_captured_signal_emitted(self):
        f = make_filter(nFrames=2)
        spy = QtTest.QSignalSpy(f.captured)
        _capture(f, _DARK)
        self.assertEqual(len(spy), 1)

    def test_captured_signal_not_emitted_before_complete(self):
        f = make_filter(nFrames=4)
        spy = QtTest.QSignalSpy(f.captured)
        f.capture()
        f.add(_DARK)
        self.assertEqual(len(spy), 0)

    def test_accumulator_cleared_after_capture(self):
        f = make_filter(nFrames=2)
        _capture(f, _DARK)
        self.assertIsNone(f._accumulator)


class TestDarkFrameFilterGet(unittest.TestCase):

    def test_get_before_add_returns_none(self):
        f = make_filter()
        self.assertIsNone(f.get())

    def test_get_without_dark_returns_raw(self):
        f = make_filter()
        f.add(_BRIGHT)
        np.testing.assert_array_equal(f.get(), _BRIGHT)

    def test_get_during_capture_returns_raw(self):
        f = make_filter(nFrames=4)
        f.capture()
        f.add(_BRIGHT)
        np.testing.assert_array_equal(f.get(), _BRIGHT)

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

    def test_get_shape_mismatch_returns_raw(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        big = np.full((8, 8), 100, dtype=np.uint8)
        f.add(big)
        np.testing.assert_array_equal(f.get(), big)

    def test_get_preserves_dtype(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        f.add(_BRIGHT)
        self.assertEqual(f.get().dtype, np.uint8)


class TestDarkFrameFilterReset(unittest.TestCase):

    def test_reset_clears_dark(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        f.reset()
        self.assertIsNone(f._dark)

    def test_reset_clears_captureCount(self):
        f = make_filter(nFrames=4)
        f.capture()
        f.reset()
        self.assertEqual(f._captureCount, 0)

    def test_reset_clears_accumulator(self):
        f = make_filter(nFrames=4)
        f.capture()
        f.add(_DARK)
        f.reset()
        self.assertIsNone(f._accumulator)

    def test_get_after_reset_returns_raw(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        f.reset()
        f.add(_BRIGHT)
        np.testing.assert_array_equal(f.get(), _BRIGHT)


class TestQDarkFrameFilterInit(unittest.TestCase):

    def test_filter_is_dark_frame_filter(self):
        self.assertIsInstance(make_widget().filter, DarkFrameFilter)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Dark Frame')

    def test_has_nFramesBox(self):
        self.assertIsInstance(make_widget()._nFramesBox, SpinBox)

    def test_nFramesBox_initial_value(self):
        w = make_widget()
        self.assertEqual(w._nFramesBox.value(), w.filter.nFrames)

    def test_has_captureButton(self):
        w = make_widget()
        self.assertIsInstance(w._captureButton, QtWidgets.QPushButton)

    def test_captureButton_label(self):
        w = make_widget()
        self.assertEqual(w._captureButton.text(), 'Capture')

    def test_has_resetButton(self):
        w = make_widget()
        self.assertIsInstance(w._resetButton, QtWidgets.QPushButton)

    def test_resetButton_label(self):
        w = make_widget()
        self.assertEqual(w._resetButton.text(), 'Reset')

    def test_display_name(self):
        self.assertEqual(QDarkFrameFilter.display_name, 'Dark Frame')

    def test_display_category(self):
        self.assertEqual(QDarkFrameFilter.display_category, 'Calibration')


class TestQDarkFrameFilterSlots(unittest.TestCase):

    def test_set_nFrames_updates_filter(self):
        w = make_widget()
        w._setNFrames(8)
        self.assertEqual(w.filter.nFrames, 8)

    def test_set_nFrames_clamps_minimum(self):
        w = make_widget()
        w._setNFrames(0)
        self.assertEqual(w.filter.nFrames, 1)

    def test_capture_disables_button(self):
        w = make_widget()
        with patch.object(w.filter, 'capture'):
            w._capture()
        self.assertFalse(w._captureButton.isEnabled())

    def test_capture_calls_filter_capture(self):
        w = make_widget()
        with patch.object(w.filter, 'capture') as mock_cap:
            w._capture()
        mock_cap.assert_called_once()

    def test_on_captured_re_enables_button(self):
        w = make_widget()
        w._captureButton.setEnabled(False)
        w._onCaptured()
        self.assertTrue(w._captureButton.isEnabled())

    def test_reset_calls_filter_reset(self):
        w = make_widget()
        with patch.object(w.filter, 'reset') as mock_reset:
            w._reset()
        mock_reset.assert_called_once()

    def test_capture_button_click_disables_button(self):
        w = make_widget()
        with patch.object(w.filter, 'capture'):
            w._captureButton.clicked.emit(False)
        self.assertFalse(w._captureButton.isEnabled())

    def test_reset_button_click_calls_filter_reset(self):
        w = make_widget()
        with patch.object(w.filter, 'reset') as mock_reset:
            w._resetButton.clicked.emit(False)
        mock_reset.assert_called_once()

    def test_filter_captured_signal_re_enables_button(self):
        w = make_widget()
        w._captureButton.setEnabled(False)
        w.filter.captured.emit()
        self.assertTrue(w._captureButton.isEnabled())

    def test_call_when_unchecked_returns_frame_unchanged(self):
        w = make_widget()
        result = w(_BRIGHT)
        np.testing.assert_array_equal(result, _BRIGHT)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
