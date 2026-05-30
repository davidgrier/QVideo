'''Unit tests for FlatFieldFilter and QFlatFieldFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtTest, QtWidgets
from pyqtgraph import SpinBox
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


class TestFlatFieldFilterInit(unittest.TestCase):

    def test_default_nFrames(self):
        self.assertEqual(make_filter().nFrames, 16)

    def test_custom_nFrames(self):
        self.assertEqual(make_filter(nFrames=4).nFrames, 4)

    def test_nFrames_minimum_is_1(self):
        self.assertEqual(make_filter(nFrames=0).nFrames, 1)

    def test_not_capturing_on_init(self):
        self.assertFalse(make_filter().isCapturing)

    def test_flat_none_on_init(self):
        self.assertIsNone(make_filter()._flat)

    def test_data_none_on_init(self):
        self.assertIsNone(make_filter().data)


class TestFlatFieldFilterCapture(unittest.TestCase):

    def test_capture_starts_counting(self):
        f = make_filter(nFrames=4)
        f.capture()
        self.assertTrue(f.isCapturing)

    def test_add_decrements_count(self):
        f = make_filter(nFrames=4)
        f.capture()
        f.add(_UNIFORM)
        self.assertEqual(f._captureCount, 3)

    def test_capture_completes_after_nFrames(self):
        f = make_filter(nFrames=4)
        _capture(f, _UNIFORM)
        self.assertFalse(f.isCapturing)

    def test_flat_stored_after_capture(self):
        f = make_filter(nFrames=4)
        _capture(f, _UNIFORM)
        self.assertIsNotNone(f._flat)

    def test_flat_is_normalized_to_unit_mean(self):
        f = make_filter(nFrames=4)
        _capture(f, _UNIFORM)
        self.assertAlmostEqual(float(f._flat.mean()), 1.0, places=5)

    def test_flat_uniform_frame_is_all_ones(self):
        f = make_filter(nFrames=2)
        _capture(f, _UNIFORM)
        np.testing.assert_array_almost_equal(
            f._flat, np.ones(_SHAPE, dtype=np.float32))

    def test_flat_zero_mean_stores_none(self):
        f = make_filter(nFrames=1)
        _capture(f, np.zeros(_SHAPE, dtype=np.uint8))
        self.assertIsNone(f._flat)

    def test_captured_signal_emitted(self):
        f = make_filter(nFrames=2)
        spy = QtTest.QSignalSpy(f.captured)
        _capture(f, _UNIFORM)
        self.assertEqual(len(spy), 1)

    def test_captured_signal_not_emitted_before_complete(self):
        f = make_filter(nFrames=4)
        spy = QtTest.QSignalSpy(f.captured)
        f.capture()
        f.add(_UNIFORM)
        self.assertEqual(len(spy), 0)

    def test_accumulator_cleared_after_capture(self):
        f = make_filter(nFrames=2)
        _capture(f, _UNIFORM)
        self.assertIsNone(f._accumulator)


class TestFlatFieldFilterGet(unittest.TestCase):

    def test_get_before_add_returns_none(self):
        self.assertIsNone(make_filter().get())

    def test_get_without_flat_returns_raw(self):
        f = make_filter()
        f.add(_UNIFORM)
        np.testing.assert_array_equal(f.get(), _UNIFORM)

    def test_get_during_capture_returns_raw(self):
        f = make_filter(nFrames=4)
        f.capture()
        f.add(_UNIFORM)
        np.testing.assert_array_equal(f.get(), _UNIFORM)

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

    def test_get_shape_mismatch_returns_raw(self):
        f = make_filter(nFrames=1)
        _capture(f, _UNIFORM)
        big = np.full((8, 8), 100, dtype=np.uint8)
        f.add(big)
        np.testing.assert_array_equal(f.get(), big)

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


class TestFlatFieldFilterReset(unittest.TestCase):

    def test_reset_clears_flat(self):
        f = make_filter(nFrames=1)
        _capture(f, _UNIFORM)
        f.reset()
        self.assertIsNone(f._flat)

    def test_reset_clears_captureCount(self):
        f = make_filter(nFrames=4)
        f.capture()
        f.reset()
        self.assertEqual(f._captureCount, 0)

    def test_reset_clears_accumulator(self):
        f = make_filter(nFrames=4)
        f.capture()
        f.add(_UNIFORM)
        f.reset()
        self.assertIsNone(f._accumulator)

    def test_get_after_reset_returns_raw(self):
        f = make_filter(nFrames=1)
        _capture(f, _UNIFORM)
        f.reset()
        f.add(_BRIGHT)
        np.testing.assert_array_equal(f.get(), _BRIGHT)


class TestQFlatFieldFilterInit(unittest.TestCase):

    def test_filter_is_flat_field_filter(self):
        self.assertIsInstance(make_widget().filter, FlatFieldFilter)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Flat Field')

    def test_has_nFramesBox(self):
        self.assertIsInstance(make_widget()._nFramesBox, SpinBox)

    def test_nFramesBox_initial_value(self):
        w = make_widget()
        self.assertEqual(w._nFramesBox.value(), w.filter.nFrames)

    def test_has_captureButton(self):
        self.assertIsInstance(
            make_widget()._captureButton, QtWidgets.QPushButton)

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
        self.assertEqual(QFlatFieldFilter.display_name, 'Flat Field')

    def test_display_category(self):
        self.assertEqual(
            QFlatFieldFilter.display_category, 'Calibration')


class TestQFlatFieldFilterSlots(unittest.TestCase):

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
