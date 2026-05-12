'''Unit tests for ForegroundEstimator and QForegroundEstimator.'''
import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from qtpy import QtCore, QtWidgets
from QVideo.filters.QForegroundEstimator import (
    ForegroundEstimator, QForegroundEstimator)


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = (128 * np.ones((480, 640), dtype=np.uint8))
_BG = (128 * np.ones((480, 640), dtype=np.uint8))


def _mock_bgs(bg=_BG):
    m = MagicMock()
    m.getBackgroundImage.return_value = bg
    return m


def make_filter(**kwargs) -> ForegroundEstimator:
    with patch('cv2.createBackgroundSubtractorMOG2', return_value=_mock_bgs()), \
         patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return ForegroundEstimator(**kwargs)


def make_widget() -> QForegroundEstimator:
    with patch('cv2.createBackgroundSubtractorMOG2', return_value=_mock_bgs()), \
         patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return QForegroundEstimator(parent=None)


# ---------------------------------------------------------------------------
# ForegroundEstimator — history property
# ---------------------------------------------------------------------------

class TestForegroundEstimatorHistory(unittest.TestCase):

    def test_default_history(self):
        f = make_filter()
        self.assertEqual(f.history, 500)

    def test_custom_history(self):
        f = make_filter(history=200)
        self.assertEqual(f.history, 200)

    def test_history_setter(self):
        f = make_filter()
        f.history = 300
        self.assertEqual(f.history, 300)

    def test_negative_history_clamped_to_one(self):
        f = make_filter(history=-10)
        self.assertEqual(f.history, 1)

    def test_zero_history_clamped_to_one(self):
        f = make_filter(history=0)
        self.assertEqual(f.history, 1)

    def test_history_setter_resets_bgs(self):
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=_mock_bgs()) as mock_create, \
             patch.object(QtCore.QThread, 'start'), \
             patch.object(QtCore.QObject, 'moveToThread'):
            f = ForegroundEstimator()
            call_count = mock_create.call_count
            f.history = 100
            self.assertGreater(mock_create.call_count, call_count)


# ---------------------------------------------------------------------------
# ForegroundEstimator — varThreshold property
# ---------------------------------------------------------------------------

class TestForegroundEstimatorVarThreshold(unittest.TestCase):

    def test_default_var_threshold(self):
        f = make_filter()
        self.assertAlmostEqual(f.varThreshold, 16.0)

    def test_custom_var_threshold(self):
        f = make_filter(varThreshold=32.0)
        self.assertAlmostEqual(f.varThreshold, 32.0)

    def test_var_threshold_setter(self):
        f = make_filter()
        f.varThreshold = 8.0
        self.assertAlmostEqual(f.varThreshold, 8.0)

    def test_negative_var_threshold_clamped_to_zero(self):
        f = make_filter(varThreshold=-5.0)
        self.assertAlmostEqual(f.varThreshold, 0.0)

    def test_var_threshold_setter_resets_bgs(self):
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=_mock_bgs()) as mock_create, \
             patch.object(QtCore.QThread, 'start'), \
             patch.object(QtCore.QObject, 'moveToThread'):
            f = ForegroundEstimator()
            call_count = mock_create.call_count
            f.varThreshold = 32.0
            self.assertGreater(mock_create.call_count, call_count)


# ---------------------------------------------------------------------------
# ForegroundEstimator — mean property
# ---------------------------------------------------------------------------

class TestForegroundEstimatorMean(unittest.TestCase):

    def test_default_mean(self):
        f = make_filter()
        self.assertAlmostEqual(f.mean, 128.0)

    def test_custom_mean(self):
        f = make_filter(mean=100.0)
        self.assertAlmostEqual(f.mean, 100.0)

    def test_mean_setter(self):
        f = make_filter()
        f.mean = 64.0
        self.assertAlmostEqual(f.mean, 64.0)

    def test_mean_below_one_clamped(self):
        f = make_filter(mean=0.0)
        self.assertAlmostEqual(f.mean, 1.0)

    def test_mean_does_not_reset_bgs(self):
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=_mock_bgs()) as mock_create, \
             patch.object(QtCore.QThread, 'start'), \
             patch.object(QtCore.QObject, 'moveToThread'):
            f = ForegroundEstimator()
            call_count = mock_create.call_count
            f.mean = 64.0
            self.assertEqual(mock_create.call_count, call_count)


# ---------------------------------------------------------------------------
# ForegroundEstimator — process()
# ---------------------------------------------------------------------------

class TestForegroundEstimatorProcess(unittest.TestCase):

    def setUp(self):
        self._patch_thread = patch.object(QtCore.QThread, 'start')
        self._patch_move = patch.object(QtCore.QObject, 'moveToThread')
        self._patch_thread.start()
        self._patch_move.start()

    def tearDown(self):
        self._patch_thread.stop()
        self._patch_move.stop()

    def test_process_returns_uint8(self):
        mock_bgs = _mock_bgs(_BG)
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=mock_bgs):
            f = ForegroundEstimator()
        result = f.process(_FRAME)
        self.assertEqual(result.dtype, np.uint8)

    def test_process_returns_same_shape(self):
        mock_bgs = _mock_bgs(_BG)
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=mock_bgs):
            f = ForegroundEstimator()
        result = f.process(_FRAME)
        self.assertEqual(result.shape, _FRAME.shape)

    def test_process_calls_apply(self):
        mock_bgs = _mock_bgs(_BG)
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=mock_bgs):
            f = ForegroundEstimator()
        f.process(_FRAME)
        mock_bgs.apply.assert_called_once_with(_FRAME)

    def test_process_calls_get_background_image(self):
        mock_bgs = _mock_bgs(_BG)
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=mock_bgs):
            f = ForegroundEstimator()
        f.process(_FRAME)
        mock_bgs.getBackgroundImage.assert_called_once()

    def test_uniform_frame_equals_background_maps_to_mean(self):
        # frame == background everywhere → ratio == 1 → output == mean
        bg = np.full((4, 4), 64, dtype=np.uint8)
        frame = np.full((4, 4), 64, dtype=np.uint8)
        mock_bgs = _mock_bgs(bg)
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=mock_bgs):
            f = ForegroundEstimator(mean=128.0)
        result = f.process(frame)
        np.testing.assert_array_equal(result, np.full((4, 4), 128, dtype=np.uint8))

    def test_zero_background_pixels_produce_zero_output(self):
        bg = np.zeros((4, 4), dtype=np.uint8)
        frame = np.full((4, 4), 100, dtype=np.uint8)
        mock_bgs = _mock_bgs(bg)
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=mock_bgs):
            f = ForegroundEstimator()
        result = f.process(frame)
        np.testing.assert_array_equal(result, np.zeros((4, 4), dtype=np.uint8))

    def test_output_clipped_to_255(self):
        bg = np.full((4, 4), 1, dtype=np.uint8)
        frame = np.full((4, 4), 255, dtype=np.uint8)
        mock_bgs = _mock_bgs(bg)
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=mock_bgs):
            f = ForegroundEstimator(mean=128.0)
        result = f.process(frame)
        np.testing.assert_array_equal(result, np.full((4, 4), 255, dtype=np.uint8))

    def test_create_background_subtractor_called_with_correct_params(self):
        with patch('cv2.createBackgroundSubtractorMOG2',
                   return_value=_mock_bgs()) as mock_create:
            with patch.object(QtCore.QThread, 'start'), \
                 patch.object(QtCore.QObject, 'moveToThread'):
                ForegroundEstimator(history=200, varThreshold=8.0)
        mock_create.assert_called_with(
            history=200, varThreshold=8.0, detectShadows=False)


# ---------------------------------------------------------------------------
# QForegroundEstimator
# ---------------------------------------------------------------------------

class TestQForegroundEstimator(unittest.TestCase):

    def test_is_qvideofilter(self):
        from QVideo.lib.QVideoFilter import QVideoFilter
        widget = make_widget()
        self.assertIsInstance(widget, QVideoFilter)

    def test_filter_is_foreground_estimator(self):
        widget = make_widget()
        self.assertIsInstance(widget.filter, ForegroundEstimator)

    def test_title(self):
        widget = make_widget()
        self.assertEqual(widget.title(), 'Foreground')

    def test_initially_unchecked(self):
        widget = make_widget()
        self.assertFalse(widget.isChecked())

    def test_history_spinbox_default(self):
        widget = make_widget()
        self.assertEqual(widget._historyBox.value(), 500)

    def test_threshold_spinbox_default(self):
        widget = make_widget()
        self.assertAlmostEqual(widget._thresholdBox.value(), 16.0)

    def test_set_history_updates_filter(self):
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=_mock_bgs()):
            widget = make_widget()
            widget._setHistory(200)
        self.assertEqual(widget.filter.history, 200)

    def test_set_history_snaps_spinbox(self):
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=_mock_bgs()):
            widget = make_widget()
            widget._setHistory(0)
        self.assertEqual(widget._historyBox.value(), 1)

    def test_set_history_snap_does_not_recurse(self):
        widget = make_widget()
        call_count = []
        original = widget._setHistory
        def counting(v):
            call_count.append(v)
            original(v)
        widget._setHistory = counting
        widget._historyBox.valueChanged.disconnect()
        widget._historyBox.valueChanged.connect(widget._setHistory)
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=_mock_bgs()):
            widget._historyBox.setValue(0)
        self.assertEqual(len(call_count), 1)

    def test_set_threshold_updates_filter(self):
        widget = make_widget()
        widget._setThreshold(32.0)
        self.assertAlmostEqual(widget.filter.varThreshold, 32.0)

    def test_history_spinbox_minimum_is_one(self):
        widget = make_widget()
        self.assertEqual(widget._historyBox.opts['bounds'][0], 1)

    def test_threshold_spinbox_minimum_is_zero(self):
        widget = make_widget()
        self.assertEqual(widget._thresholdBox.opts['bounds'][0], 0.0)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)

    def test_call_when_checked_processes_frame(self):
        mock_bgs = _mock_bgs(_BG)
        with patch('cv2.createBackgroundSubtractorMOG2', return_value=mock_bgs), \
             patch.object(QtCore.QThread, 'start'), \
             patch.object(QtCore.QObject, 'moveToThread'):
            widget = QForegroundEstimator()
        widget.setChecked(True)
        result = widget(_FRAME)
        self.assertIsInstance(result, np.ndarray)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
