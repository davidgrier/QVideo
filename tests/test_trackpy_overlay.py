'''Unit tests for the trackpy particle-tracking overlay.'''
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest


import QVideo.overlays.trackpy as _mod  # noqa: E402
from QVideo.overlays.trackpy import (  # noqa: E402
    _TrackpyWorker, QTrackpyOverlay, QTrackpyWidget,
)

# Replace the module-level tp binding with a mock so tests never
# touch real trackpy (which may be absent or broken on this host).
mock_tp = MagicMock()
_mod.tp = mock_tp

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_frame(color: bool = False) -> np.ndarray:
    shape = (64, 64, 3) if color else (64, 64)
    return np.zeros(shape, dtype=np.uint8)


def _make_features(n: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        'x': rng.uniform(0, 64, n),
        'y': rng.uniform(0, 64, n),
        'mass': rng.uniform(100, 500, n),
    })


class MockSource(QtCore.QObject):
    newFrame = QtCore.pyqtSignal(np.ndarray)


# ---------------------------------------------------------------------------
# _TrackpyWorker
# ---------------------------------------------------------------------------

class TestTrackpyWorkerInit(unittest.TestCase):

    def test_raises_when_trackpy_missing(self):
        with patch.object(_mod, 'tp', None):
            with self.assertRaises(ImportError):
                _TrackpyWorker()


class TestTrackpyWorkerDiameter(unittest.TestCase):

    def test_odd_diameter_unchanged(self):
        w = _TrackpyWorker(diameter=11)
        self.assertEqual(w.diameter, 11)

    def test_even_diameter_rounded_up_to_odd(self):
        w = _TrackpyWorker(diameter=10)
        self.assertEqual(w.diameter, 11)

    def test_diameter_setter_enforces_odd(self):
        w = _TrackpyWorker()
        w.diameter = 8
        self.assertEqual(w.diameter, 9)


class TestTrackpyWorkerLocate(unittest.TestCase):

    def setUp(self):
        mock_tp.reset_mock()
        self._worker = _TrackpyWorker(diameter=11, minmass=50.)

    def _collect(self, n: int = 1):
        spy = QtTest.QSignalSpy(self._worker.newData)
        return spy

    def test_locate_calls_trackpy(self):
        frame = _make_frame()
        mock_tp.locate.return_value = _make_features()
        spy = self._collect()
        self._worker.locate(frame)
        mock_tp.locate.assert_called_once()
        args, kwargs = mock_tp.locate.call_args
        self.assertEqual(args[0].ndim, 2)
        self.assertEqual(args[1], 11)
        self.assertEqual(kwargs['minmass'], 50.)

    def test_locate_emits_features(self):
        features = _make_features()
        mock_tp.locate.return_value = features
        spy = self._collect()
        self._worker.locate(_make_frame())
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], features)

    def test_locate_converts_colour_to_grey(self):
        mock_tp.locate.return_value = _make_features()
        self._worker.locate(_make_frame(color=True))
        args, _ = mock_tp.locate.call_args
        self.assertEqual(args[0].ndim, 2)

    def test_locate_passes_greyscale_unchanged(self):
        frame = _make_frame()
        mock_tp.locate.return_value = _make_features()
        self._worker.locate(frame)
        args, _ = mock_tp.locate.call_args
        np.testing.assert_array_equal(args[0], frame)

    def test_locate_emits_none_on_exception(self):
        mock_tp.locate.side_effect = RuntimeError('oops')
        spy = self._collect()
        self._worker.locate(_make_frame())
        self.assertEqual(len(spy), 1)
        self.assertIsNone(spy[0][0])


# ---------------------------------------------------------------------------
# QTrackpyOverlay
# ---------------------------------------------------------------------------

class TestQTrackpyOverlay(unittest.TestCase):

    def setUp(self):
        self._overlay = QTrackpyOverlay()

    def test_set_features_with_data(self):
        features = _make_features(5)
        self._overlay.setFeatures(features)
        pts = self._overlay.getData()
        np.testing.assert_array_almost_equal(pts[0], features['x'].to_numpy())
        np.testing.assert_array_almost_equal(pts[1], features['y'].to_numpy())

    def test_set_features_none_clears_overlay(self):
        self._overlay.setFeatures(_make_features())
        self._overlay.setFeatures(None)
        pts = self._overlay.getData()
        self.assertEqual(len(pts[0]), 0)

    def test_set_features_empty_df_clears_overlay(self):
        self._overlay.setFeatures(_make_features())
        self._overlay.setFeatures(pd.DataFrame({'x': [], 'y': []}))
        pts = self._overlay.getData()
        self.assertEqual(len(pts[0]), 0)

    def test_initially_hidden(self):
        overlay = QTrackpyOverlay()
        # ScatterPlotItem is visible by default; QTrackpyWidget hides it
        # This tests the standalone item has no forced hidden state.
        self.assertTrue(overlay.isVisible())


# ---------------------------------------------------------------------------
# QTrackpyWidget
# ---------------------------------------------------------------------------

def _make_widget(**kwargs):
    '''Create a QTrackpyWidget with the background thread neutralised.

    Patches moveToThread (so the worker stays on the main thread) and
    QThread.start (so no OS thread is actually spawned).
    '''
    with patch.object(_TrackpyWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'):
        w = QTrackpyWidget(**kwargs)
    return w


class TestQTrackpyWidgetInit(unittest.TestCase):

    def test_initially_unchecked(self):
        w = _make_widget()
        self.assertFalse(w.isChecked())

    def test_no_source_by_default(self):
        w = _make_widget()
        self.assertIsNone(w.source)

    def test_initial_diameter_reflected_in_spinbox(self):
        w = _make_widget(diameter=15)
        self.assertEqual(w._diameterSpinBox.value(), 15)

    def test_initial_minmass_reflected_in_spinbox(self):
        w = _make_widget(minmass=200.)
        self.assertAlmostEqual(w._minmassSpinBox.value(), 200.)


class TestQTrackpyWidgetSource(unittest.TestCase):

    def test_source_setter_connects_newframe(self):
        w = _make_widget()
        src = MockSource()
        w.source = src
        self.assertIs(w.source, src)

    def test_source_setter_none_after_source(self):
        w = _make_widget()
        src = MockSource()
        w.source = src
        w.source = None
        self.assertIsNone(w.source)

    def test_source_replacement_disconnects_old(self):
        w = _make_widget()
        src1 = MockSource()
        src2 = MockSource()
        w.source = src1
        w.source = src2
        # src1.newFrame should no longer reach the worker
        spy = QtTest.QSignalSpy(w.newData)
        w.setChecked(True)
        src1.newFrame.emit(_make_frame())
        QtWidgets.QApplication.processEvents()
        self.assertEqual(len(spy), 0)


class TestQTrackpyWidgetNewFrame(unittest.TestCase):

    def setUp(self):
        self._w = _make_widget()
        mock_tp.reset_mock()
        mock_tp.locate.return_value = _make_features()

    def test_new_frame_ignored_when_unchecked(self):
        spy = QtTest.QSignalSpy(self._w._locate)
        self._w._onNewFrame(_make_frame())
        self.assertEqual(len(spy), 0)

    def test_new_frame_dispatched_when_checked_and_ready(self):
        self._w.setChecked(True)
        spy = QtTest.QSignalSpy(self._w._locate)
        self._w._onNewFrame(_make_frame())
        self.assertEqual(len(spy), 1)

    def test_ready_flag_cleared_before_dispatch(self):
        # Break the sync round-trip so we can inspect _ready mid-flight.
        self._w.setChecked(True)
        self._w._locate.disconnect(self._w._worker.locate)
        try:
            self._w._onNewFrame(_make_frame())
            self.assertFalse(self._w._ready)
        finally:
            self._w._locate.connect(self._w._worker.locate)

    def test_second_frame_dropped_while_busy(self):
        self._w.setChecked(True)
        self._w._ready = False   # simulate worker still running
        spy = QtTest.QSignalSpy(self._w._locate)
        self._w._onNewFrame(_make_frame())
        self.assertEqual(len(spy), 0)


class TestQTrackpyWidgetNewData(unittest.TestCase):

    def setUp(self):
        self._w = _make_widget()
        self._w._ready = False  # simulate in-flight request

    def test_ready_flag_restored(self):
        self._w._onNewData(_make_features())
        self.assertTrue(self._w._ready)

    def test_new_data_signal_emitted(self):
        spy = QtTest.QSignalSpy(self._w.newData)
        features = _make_features()
        self._w._onNewData(features)
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], features)

    def test_overlay_updated(self):
        features = _make_features(4)
        self._w._onNewData(features)
        pts = self._w._overlay.getData()
        self.assertEqual(len(pts[0]), 4)

    def test_none_features_clears_overlay(self):
        self._w._overlay.setFeatures(_make_features())
        self._w._onNewData(None)
        pts = self._w._overlay.getData()
        self.assertEqual(len(pts[0]), 0)


class TestQTrackpyWidgetOverlay(unittest.TestCase):

    def test_overlay_returns_qtrackpyoverlay(self):
        w = _make_widget()
        self.assertIsInstance(w.overlay, QTrackpyOverlay)


class TestQTrackpyWidgetDiameter(unittest.TestCase):

    def test_set_odd_diameter(self):
        w = _make_widget()
        w._setDiameter(13)
        self.assertEqual(w._worker.diameter, 13)

    def test_set_even_diameter_rounds_to_odd(self):
        w = _make_widget()
        w._setDiameter(12)
        self.assertEqual(w._worker.diameter, 13)

    def test_spinbox_corrected_on_even_input(self):
        w = _make_widget()
        w._setDiameter(12)
        self.assertEqual(w._diameterSpinBox.value(), 13)


class TestQTrackpyWidgetMinmass(unittest.TestCase):

    def test_set_minmass(self):
        w = _make_widget()
        w._setMinmass(250.)
        self.assertAlmostEqual(w._worker.minmass, 250.)


class TestQTrackpyWidgetCleanup(unittest.TestCase):

    def test_cleanup_disconnects_source(self):
        w = _make_widget()
        src = MockSource()
        w.source = src
        w._cleanup()
        self.assertIsNone(w.source)

    def test_cleanup_stops_thread(self):
        w = _make_widget()
        thread = w._thread
        thread.quit = MagicMock()
        thread.wait = MagicMock()
        w._cleanup()
        thread.quit.assert_called_once()
        thread.wait.assert_called_once()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
