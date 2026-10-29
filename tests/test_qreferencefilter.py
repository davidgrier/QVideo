'''Unit tests for ReferenceFilter and QReferenceFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtWidgets
from pyqtgraph import SpinBox
from QVideo.tests.signals import record
from QVideo.lib import ReferenceFilter, QReferenceFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_SHAPE = (4, 4)
_DARK = np.full(_SHAPE, 20, dtype=np.uint8)
_BRIGHT = np.full(_SHAPE, 100, dtype=np.uint8)


class _Bias(ReferenceFilter):
    '''The smallest reference filter: subtract the average.'''

    def _makeReference(self, mean):
        return mean

    def _correct(self, frame, reference):
        corrected = frame.astype(np.float32) - reference
        return np.clip(corrected, 0, 255).astype(np.uint8)


class _QBias(QReferenceFilter):
    display_name = 'Bias'
    filterClass = _Bias


def make_filter(**kwargs) -> _Bias:
    return _Bias(**kwargs)


def make_widget() -> _QBias:
    return _QBias(parent=None)


def _capture(f: ReferenceFilter, frame: np.ndarray) -> None:
    '''Drive a complete capture cycle on f using frame.'''
    f.capture()
    for _ in range(f.nFrames):
        f.add(frame)


class TestReferenceFilterInit(unittest.TestCase):

    def test_default_nFrames(self):
        self.assertEqual(make_filter().nFrames, 16)

    def test_custom_nFrames(self):
        self.assertEqual(make_filter(nFrames=8).nFrames, 8)

    def test_nFrames_minimum_is_1(self):
        self.assertEqual(make_filter(nFrames=0).nFrames, 1)

    def test_not_capturing_on_init(self):
        self.assertFalse(make_filter().isCapturing)

    def test_no_reference_on_init(self):
        self.assertIsNone(make_filter().reference)

    def test_data_none_on_init(self):
        self.assertIsNone(make_filter().data)


class TestReferenceFilterHooks(unittest.TestCase):

    def test_a_subclass_must_say_what_the_reference_is(self):
        with self.assertRaises(NotImplementedError):
            ReferenceFilter()._makeReference(_DARK)

    def test_a_subclass_must_say_how_to_correct(self):
        with self.assertRaises(NotImplementedError):
            ReferenceFilter()._correct(_DARK, _DARK)


class TestReferenceFilterCapture(unittest.TestCase):

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
        f = make_filter(nFrames=3)
        _capture(f, _DARK)
        self.assertFalse(f.isCapturing)

    def test_reference_is_made_by_the_subclass(self):
        f = make_filter(nFrames=2)
        _capture(f, _DARK)
        np.testing.assert_array_equal(f.reference, _DARK)

    def test_reference_is_the_mean_of_the_frames(self):
        f = make_filter(nFrames=2)
        f.capture()
        f.add(np.full(_SHAPE, 10, dtype=np.uint8))
        f.add(np.full(_SHAPE, 30, dtype=np.uint8))
        np.testing.assert_array_equal(f.reference, np.full(_SHAPE, 20))

    def test_the_old_reference_stays_until_the_capture_completes(self):
        f = make_filter(nFrames=2)
        _capture(f, _DARK)
        f.capture()
        f.add(_BRIGHT)
        np.testing.assert_array_equal(f.reference, _DARK)

    def test_a_subclass_that_has_no_reference_leaves_none(self):
        class _Unusable(_Bias):
            def _makeReference(self, mean):
                return None
        f = _Unusable(nFrames=1)
        _capture(f, _DARK)
        self.assertIsNone(f.reference)

    def test_captured_signal_emitted(self):
        f = make_filter(nFrames=2)
        spy = record(f.captured)
        _capture(f, _DARK)
        self.assertEqual(len(spy), 1)

    def test_captured_signal_not_emitted_before_complete(self):
        f = make_filter(nFrames=4)
        spy = record(f.captured)
        f.capture()
        f.add(_DARK)
        self.assertEqual(len(spy), 0)

    def test_accumulator_cleared_after_capture(self):
        f = make_filter(nFrames=2)
        _capture(f, _DARK)
        self.assertIsNone(f._accumulator)


class TestReferenceFilterGet(unittest.TestCase):

    def test_get_before_add_returns_none(self):
        self.assertIsNone(make_filter().get())

    def test_get_without_reference_returns_raw(self):
        f = make_filter()
        f.add(_BRIGHT)
        np.testing.assert_array_equal(f.get(), _BRIGHT)

    def test_get_during_capture_returns_raw(self):
        f = make_filter(nFrames=4)
        f.capture()
        f.add(_BRIGHT)
        np.testing.assert_array_equal(f.get(), _BRIGHT)

    def test_get_corrects_with_the_reference(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        f.add(_BRIGHT)
        np.testing.assert_array_equal(f.get(), _BRIGHT - _DARK)

    def test_get_shape_mismatch_returns_raw(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        other = np.full((2, 2), 50, dtype=np.uint8)
        f.add(other)
        np.testing.assert_array_equal(f.get(), other)

    def test_a_filter_can_be_called_like_a_function(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        np.testing.assert_array_equal(f(_BRIGHT), _BRIGHT - _DARK)


class TestReferenceFilterReset(unittest.TestCase):

    def test_reset_clears_reference(self):
        f = make_filter(nFrames=1)
        _capture(f, _DARK)
        f.reset()
        self.assertIsNone(f.reference)

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


class TestQReferenceFilterInit(unittest.TestCase):

    def test_the_widget_makes_its_filter(self):
        self.assertIsInstance(make_widget().filter, _Bias)

    def test_the_title_is_the_display_name(self):
        self.assertEqual(make_widget().title(), 'Bias')

    def test_has_nFramesBox(self):
        self.assertIsInstance(make_widget()._nFramesBox, SpinBox)

    def test_nFramesBox_initial_value(self):
        w = make_widget()
        self.assertEqual(w._nFramesBox.value(), w.filter.nFrames)

    def test_has_captureButton(self):
        w = make_widget()
        self.assertIsInstance(w._captureButton, QtWidgets.QPushButton)
        self.assertEqual(w._captureButton.text(), 'Capture')

    def test_has_resetButton(self):
        w = make_widget()
        self.assertIsInstance(w._resetButton, QtWidgets.QPushButton)
        self.assertEqual(w._resetButton.text(), 'Reset')

    def test_the_category_is_calibration(self):
        self.assertEqual(QReferenceFilter.display_category, 'Calibration')

    def test_the_base_widget_is_not_offered_in_the_picker(self):
        self.assertEqual(QReferenceFilter.display_name, '')


class TestQReferenceFilterSlots(unittest.TestCase):

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
            w._captureButton.click()
        self.assertFalse(w._captureButton.isEnabled())

    def test_reset_button_click_calls_filter_reset(self):
        w = make_widget()
        with patch.object(w.filter, 'reset') as mock_reset:
            w._resetButton.setEnabled(True)
            w._resetButton.click()
        mock_reset.assert_called_once()

    def test_filter_captured_signal_re_enables_button(self):
        w = make_widget()
        w._captureButton.setEnabled(False)
        w.filter.captured.emit()
        self.assertTrue(w._captureButton.isEnabled())

    def test_call_when_unchecked_returns_frame_unchanged(self):
        w = make_widget()
        np.testing.assert_array_equal(w(_BRIGHT), _BRIGHT)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
