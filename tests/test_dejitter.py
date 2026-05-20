'''Unit tests for DejitterFilter and QDejitterFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.filters.dejitter import DejitterFilter, QDejitterFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# 32x32 grayscale — power-of-2 size gives phaseCorrelate reliable results
_SHAPE = (32, 32)
_REF = np.zeros(_SHAPE, dtype=np.uint8)
_REF[12:20, 12:20] = 255           # white square, centred

_SHIFTED = np.zeros(_SHAPE, dtype=np.uint8)
_SHIFTED[12:20, 15:23] = 255       # same square shifted right by 3 px

_COLOR = np.zeros((*_SHAPE, 3), dtype=np.uint8)
_COLOR[12:20, 12:20] = [255, 128, 64]


def make_filter(**kwargs) -> DejitterFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return DejitterFilter(**kwargs)


def make_widget() -> QDejitterFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return QDejitterFilter(parent=None)


class TestDejitterFilterInit(unittest.TestCase):

    def setUp(self):
        self._p_start = patch.object(QtCore.QThread, 'start')
        self._p_move = patch.object(QtCore.QObject, 'moveToThread')
        self._p_start.start()
        self._p_move.start()

    def tearDown(self):
        self._p_start.stop()
        self._p_move.stop()

    def test_is_async_video_filter(self):
        self.assertIsInstance(DejitterFilter(), AsyncVideoFilter)

    def test_default_mode(self):
        self.assertEqual(DejitterFilter().mode, 'static')

    def test_default_alpha(self):
        self.assertAlmostEqual(DejitterFilter().alpha, 0.05)

    def test_custom_mode(self):
        self.assertEqual(DejitterFilter(mode='rolling').mode, 'rolling')

    def test_custom_alpha(self):
        self.assertAlmostEqual(DejitterFilter(alpha=0.2).alpha, 0.2)

    def test_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            DejitterFilter(mode='bilateral')


class TestDejitterFilterMode(unittest.TestCase):

    def test_mode_setter_valid(self):
        f = make_filter()
        f.mode = 'rolling'
        self.assertEqual(f.mode, 'rolling')

    def test_mode_setter_invalid_raises(self):
        f = make_filter()
        with self.assertRaises(ValueError):
            f.mode = 'unknown'

    def test_mode_change_resets_reference(self):
        f = make_filter()
        f.process(_REF)             # seeds reference
        self.assertIsNotNone(f._reference)
        f.mode = 'rolling'
        self.assertIsNone(f._reference)


class TestDejitterFilterAlpha(unittest.TestCase):

    def test_alpha_setter(self):
        f = make_filter()
        f.alpha = 0.3
        self.assertAlmostEqual(f.alpha, 0.3)

    def test_alpha_clamped_to_one(self):
        f = make_filter()
        f.alpha = 2.0
        self.assertAlmostEqual(f.alpha, 1.0)

    def test_alpha_clamped_above_zero(self):
        f = make_filter()
        f.alpha = 0.0
        self.assertGreater(f.alpha, 0.0)


class TestDejitterFilterProcess(unittest.TestCase):

    def test_first_frame_returned_unchanged(self):
        f = make_filter()
        result = f.process(_REF)
        np.testing.assert_array_equal(result, _REF)

    def test_output_shape_matches_input(self):
        f = make_filter()
        f.process(_REF)
        result = f.process(_SHIFTED)
        self.assertEqual(result.shape, _SHAPE)

    def test_output_dtype_matches_input(self):
        f = make_filter()
        f.process(_REF)
        result = f.process(_SHIFTED)
        self.assertEqual(result.dtype, np.uint8)

    def test_color_input_preserved(self):
        f = make_filter()
        f.process(_COLOR)
        result = f.process(_COLOR)
        self.assertEqual(result.ndim, 3)
        self.assertEqual(result.shape[2], 3)

    def test_static_corrects_known_shift(self):
        '''Corrected output should be closer to the reference than the raw shift.'''
        f = make_filter(mode='static')
        f.process(_REF)
        corrected = f.process(_SHIFTED)
        diff_input = np.abs(_SHIFTED.astype(int) - _REF.astype(int)).mean()
        diff_corrected = np.abs(corrected.astype(int) - _REF.astype(int)).mean()
        self.assertLess(diff_corrected, diff_input)

    def test_shape_change_reinitializes(self):
        f = make_filter()
        f.process(_REF)
        small = np.zeros((16, 16), dtype=np.uint8)
        result = f.process(small)
        self.assertEqual(result.shape, (16, 16))

    def test_rolling_updates_reference(self):
        f = make_filter(mode='rolling', alpha=1.0)
        f.process(_REF)
        ref_before = f._reference.copy()
        f.process(_SHIFTED)
        self.assertFalse(np.array_equal(f._reference, ref_before))

    def test_static_does_not_update_reference(self):
        f = make_filter(mode='static')
        f.process(_REF)
        ref_before = f._reference.copy()
        f.process(_SHIFTED)
        np.testing.assert_array_equal(f._reference, ref_before)


class TestDejitterFilterReset(unittest.TestCase):

    def test_reset_clears_reference(self):
        f = make_filter()
        f.process(_REF)
        f.reset()
        self.assertIsNone(f._reference)

    def test_reset_clears_result(self):
        f = make_filter()
        f(_REF)
        f(_SHIFTED)
        f.reset()
        self.assertIsNone(f._result)

    def test_first_frame_after_reset_returns_unchanged(self):
        f = make_filter()
        f.process(_REF)
        f.process(_SHIFTED)
        f.reset()
        result = f.process(_REF)
        np.testing.assert_array_equal(result, _REF)


class TestQDejitterFilter(unittest.TestCase):

    def setUp(self):
        self._p_start = patch.object(QtCore.QThread, 'start')
        self._p_move = patch.object(QtCore.QObject, 'moveToThread')
        self._p_start.start()
        self._p_move.start()

    def tearDown(self):
        self._p_start.stop()
        self._p_move.stop()

    def test_filter_is_dejitter_filter(self):
        self.assertIsInstance(QDejitterFilter().filter, DejitterFilter)

    def test_title(self):
        self.assertEqual(QDejitterFilter().title(), 'Dejitter')

    def test_alpha_spinbox_hidden_in_static_mode(self):
        w = QDejitterFilter()
        self.assertTrue(w._alphaBox.isHidden())

    def test_alpha_spinbox_visible_in_rolling_mode(self):
        w = QDejitterFilter()
        w._setMode('Rolling')
        self.assertFalse(w._alphaBox.isHidden())

    def test_set_mode_updates_filter(self):
        w = QDejitterFilter()
        w._setMode('Rolling')
        self.assertEqual(w.filter.mode, 'rolling')

    def test_set_alpha_updates_filter(self):
        w = QDejitterFilter()
        w._setAlpha(0.2)
        self.assertAlmostEqual(w.filter.alpha, 0.2)

    def test_reset_button_clears_reference(self):
        w = QDejitterFilter()
        w.filter.process(_REF)
        w._resetReference()
        self.assertIsNone(w.filter._reference)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        w = QDejitterFilter()
        result = w(_REF)
        np.testing.assert_array_equal(result, _REF)

    def test_call_when_checked_returns_ndarray(self):
        w = QDejitterFilter()
        w.setChecked(True)
        result = w(_REF)
        self.assertIsInstance(result, np.ndarray)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
