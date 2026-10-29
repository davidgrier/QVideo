'''Unit tests for the trackpy particle-tracking overlay.'''
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
from qtpy import QtCore, QtWidgets


from QVideo.tests.signals import record
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
    newFrame = QtCore.Signal(np.ndarray)


# ---------------------------------------------------------------------------
# _TrackpyWorker
# ---------------------------------------------------------------------------

class TestTrackpyWorkerInit(unittest.TestCase):

    def test_raises_when_trackpy_missing(self):
        with patch.object(_mod, 'tp', None):
            with self.assertRaises(ImportError):
                _TrackpyWorker()

    def test_the_error_names_why_the_import_failed(self):
        broken = RuntimeError('numba is broken')
        with patch.object(_mod, 'tp', None), \
                patch.object(_mod, '_importError', broken):
            with self.assertRaises(ImportError) as caught:
                _TrackpyWorker()
        self.assertIs(caught.exception.__cause__, broken)


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
        spy = record(self._worker.newData)
        return spy

    def test_locate_calls_trackpy(self):
        frame = _make_frame()
        mock_tp.locate.return_value = _make_features()
        spy = self._collect()
        self._worker.process(frame)
        mock_tp.locate.assert_called_once()
        args, kwargs = mock_tp.locate.call_args
        self.assertEqual(args[0].ndim, 2)
        self.assertEqual(args[1], 11)
        self.assertEqual(kwargs['minmass'], 50.)
        self.assertFalse(kwargs['characterize'])
        self.assertFalse(kwargs['invert'])

    def test_locate_emits_features(self):
        features = _make_features()
        mock_tp.locate.return_value = features
        spy = self._collect()
        self._worker.process(_make_frame())
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], features)

    def test_locate_converts_color_to_gray(self):
        mock_tp.locate.return_value = _make_features()
        self._worker.process(_make_frame(color=True))
        args, _ = mock_tp.locate.call_args
        self.assertEqual(args[0].ndim, 2)

    def test_locate_passes_grayscale_unchanged(self):
        frame = _make_frame()
        mock_tp.locate.return_value = _make_features()
        self._worker.process(frame)
        args, _ = mock_tp.locate.call_args
        np.testing.assert_array_equal(args[0], frame)

    def test_locate_emits_none_on_exception(self):
        mock_tp.locate.side_effect = RuntimeError('oops')
        spy = self._collect()
        self._worker.process(_make_frame())
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
    '''Create a QTrackpyWidget with the background thread neutralized.

    Patches moveToThread (so the worker stays on the main thread) and
    QThread.start (so no OS thread is actually spawned).
    '''
    with patch.object(_TrackpyWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'):
        w = QTrackpyWidget(**kwargs)
    return w


class TestQTrackpyWidgetInit(unittest.TestCase):

    def test_initial_diameter_reflected_in_spinbox(self):
        w = _make_widget(diameter=15)
        self.assertEqual(w._diameterSpinBox.value(), 15)

    def test_initial_minmass_reflected_in_spinbox(self):
        w = _make_widget(minmass=200.)
        self.assertAlmostEqual(w._minmassSpinBox.value(), 200.)


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


class TestTrackpyWorkerOpts(unittest.TestCase):

    def test_characterize_false_by_default(self):
        w = _TrackpyWorker()
        self.assertFalse(w._opts['characterize'])

    def test_separation_none_by_default(self):
        w = _TrackpyWorker()
        self.assertIsNone(w._opts['separation'])

    def test_noise_size_one_by_default(self):
        w = _TrackpyWorker()
        self.assertEqual(w._opts['noise_size'], 1)

    def test_invert_false_by_default(self):
        w = _TrackpyWorker()
        self.assertFalse(w._opts['invert'])

    def test_minmass_in_opts(self):
        w = _TrackpyWorker(minmass=75.)
        self.assertAlmostEqual(w._opts['minmass'], 75.)

    def test_minmass_property_reads_opts(self):
        w = _TrackpyWorker(minmass=50.)
        w._opts['minmass'] = 99.
        self.assertAlmostEqual(w.minmass, 99.)

    def test_minmass_property_writes_opts(self):
        w = _TrackpyWorker()
        w.minmass = 42.
        self.assertAlmostEqual(w._opts['minmass'], 42.)


class TestTrackpyWorkerOptions(unittest.TestCase):
    '''The options of the worker are properties, not a dict to poke.'''

    def test_the_constructor_sets_the_options(self):
        worker = _TrackpyWorker(7, 50., separation=9., noiseSize=2,
                                invert=True)
        self.assertEqual(worker.diameter, 7)
        self.assertEqual(worker._opts['minmass'], 50.)
        self.assertEqual(worker._opts['separation'], 9.)
        self.assertEqual(worker._opts['noise_size'], 2)
        self.assertTrue(worker._opts['invert'])

    def test_each_option_reads_what_locate_gets(self):
        worker = _TrackpyWorker()
        for name, key, value in (('minmass', 'minmass', 5.),
                                 ('separation', 'separation', 12.),
                                 ('noiseSize', 'noise_size', 3),
                                 ('invert', 'invert', True)):
            with self.subTest(name):
                setattr(worker, name, value)
                self.assertEqual(worker._opts[key], value)
                self.assertEqual(getattr(worker, name), value)


class TestQTrackpyWidgetMinmass(unittest.TestCase):

    def test_set_minmass(self):
        w = _make_widget()
        w._setMinmass(250.)
        self.assertAlmostEqual(w._worker.minmass, 250.)


class TestQTrackpyWidgetSeparation(unittest.TestCase):

    def test_separation_spinbox_exists(self):
        w = _make_widget()
        self.assertIsInstance(w._separationSpinBox, QtWidgets.QDoubleSpinBox)

    def test_separation_spinbox_zero_by_default(self):
        w = _make_widget()
        self.assertAlmostEqual(w._separationSpinBox.value(), 0.)

    def test_separation_spinbox_init_value(self):
        w = _make_widget(separation=8.)
        self.assertAlmostEqual(w._separationSpinBox.value(), 8.)

    def test_set_separation_zero_stores_none(self):
        w = _make_widget()
        w._setSeparation(0.)
        self.assertIsNone(w._worker._opts['separation'])

    def test_set_separation_nonzero(self):
        w = _make_widget()
        w._setSeparation(12.)
        self.assertAlmostEqual(w._worker._opts['separation'], 12.)


class TestQTrackpyWidgetNoiseSize(unittest.TestCase):

    def test_noise_size_spinbox_exists(self):
        w = _make_widget()
        self.assertIsInstance(w._noiseSizeSpinBox, QtWidgets.QSpinBox)

    def test_noise_size_spinbox_default(self):
        w = _make_widget()
        self.assertEqual(w._noiseSizeSpinBox.value(), 1)

    def test_noise_size_spinbox_init_value(self):
        w = _make_widget(noise_size=3)
        self.assertEqual(w._noiseSizeSpinBox.value(), 3)

    def test_set_noise_size(self):
        w = _make_widget()
        w._setNoiseSize(4)
        self.assertEqual(w._worker._opts['noise_size'], 4)


class TestQTrackpyWidgetInvert(unittest.TestCase):

    def test_invert_checkbox_exists(self):
        w = _make_widget()
        self.assertIsInstance(w._invertCheckBox, QtWidgets.QCheckBox)

    def test_invert_unchecked_by_default(self):
        w = _make_widget()
        self.assertFalse(w._invertCheckBox.isChecked())

    def test_invert_checked_when_init_true(self):
        w = _make_widget(invert=True)
        self.assertTrue(w._invertCheckBox.isChecked())

    def test_set_invert_true(self):
        w = _make_widget()
        w._setInvert(True)
        self.assertTrue(w._worker._opts['invert'])

    def test_set_invert_false(self):
        w = _make_widget(invert=True)
        w._setInvert(False)
        self.assertFalse(w._worker._opts['invert'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
