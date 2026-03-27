'''Unit tests for the YOLO object-detection overlay.'''
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

import QVideo.overlays.yolo as _mod  # noqa: E402
from QVideo.overlays.yolo import (  # noqa: E402
    _YoloWorker, QYoloOverlay, QYoloWidget,
)

# Replace module-level YOLO with a mock so tests never touch real ultralytics.
mock_YOLO_cls = MagicMock()
_mod.YOLO = mock_YOLO_cls


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_frame() -> np.ndarray:
    return np.zeros((64, 64, 3), dtype=np.uint8)


def _make_features(n: int = 2) -> pd.DataFrame:
    return pd.DataFrame({
        'x1': [10., 30.],
        'y1': [10., 30.],
        'x2': [20., 50.],
        'y2': [20., 50.],
        'confidence': [0.9, 0.7],
        'class': [0, 1],
        'label': ['cat', 'dog'],
    })[:n]


def _make_mock_results(n: int = 2):
    '''Return a mock ultralytics Results list with n detections.'''
    boxes = MagicMock()
    boxes.__len__ = MagicMock(return_value=n)
    xyxy = np.array([[10, 10, 20, 20], [30, 30, 50, 50]], dtype=np.float32)[:n]
    conf = np.array([0.9, 0.7], dtype=np.float32)[:n]
    cls = np.array([0, 1], dtype=np.float32)[:n]
    boxes.xyxy.cpu().numpy.return_value = xyxy
    boxes.conf.cpu().numpy.return_value = conf
    boxes.cls.cpu().numpy.return_value = cls
    result = MagicMock()
    result.boxes = boxes
    result.names = {0: 'cat', 1: 'dog'}
    return [result]


class MockSource(QtCore.QObject):
    newFrame = QtCore.pyqtSignal(np.ndarray)


class MockScreen:
    def __init__(self):
        self.view = MagicMock()
        self.addOverlay = MagicMock()
        self.removeOverlay = MagicMock()


def _make_widget(**kwargs):
    '''Create a QYoloWidget with the background thread neutralised.'''
    with patch.object(_YoloWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'):
        w = QYoloWidget(**kwargs)
    return w


# ---------------------------------------------------------------------------
# _YoloWorker
# ---------------------------------------------------------------------------

class TestYoloWorkerInit(unittest.TestCase):

    def setUp(self):
        mock_YOLO_cls.reset_mock()

    def test_loads_model(self):
        _YoloWorker()
        mock_YOLO_cls.assert_called_once_with('yolo11n.pt')

    def test_custom_model_name(self):
        _YoloWorker(model_name='yolo11s.pt')
        mock_YOLO_cls.assert_called_once_with('yolo11s.pt')

    def test_raises_when_yolo_missing(self):
        with patch.object(_mod, 'YOLO', None):
            with self.assertRaises(ImportError):
                _YoloWorker()

    def test_raises_on_missing_model_file(self):
        mock_YOLO_cls.side_effect = FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            _YoloWorker()
        mock_YOLO_cls.side_effect = None


class TestYoloWorkerDetect(unittest.TestCase):

    def setUp(self):
        mock_YOLO_cls.reset_mock()
        self._worker = _YoloWorker()
        self._worker.model = MagicMock()

    def test_detect_emits_dataframe_on_detections(self):
        self._worker.model.return_value = _make_mock_results(2)
        spy = QtTest.QSignalSpy(self._worker.newData)
        self._worker.detect(_make_frame())
        self.assertEqual(len(spy), 1)
        features = spy[0][0]
        self.assertIsNotNone(features)
        self.assertEqual(len(features), 2)

    def test_detect_emits_none_on_no_detections(self):
        self._worker.model.return_value = _make_mock_results(0)
        spy = QtTest.QSignalSpy(self._worker.newData)
        self._worker.detect(_make_frame())
        self.assertEqual(len(spy), 1)
        self.assertIsNone(spy[0][0])

    def test_detect_emits_none_on_exception(self):
        self._worker.model.side_effect = RuntimeError('oops')
        spy = QtTest.QSignalSpy(self._worker.newData)
        self._worker.detect(_make_frame())
        self.assertEqual(len(spy), 1)
        self.assertIsNone(spy[0][0])

    def test_detect_dataframe_has_expected_columns(self):
        self._worker.model.return_value = _make_mock_results(1)
        spy = QtTest.QSignalSpy(self._worker.newData)
        self._worker.detect(_make_frame())
        features = spy[0][0]
        for col in ('x1', 'y1', 'x2', 'y2', 'confidence', 'class', 'label'):
            self.assertIn(col, features.columns)

    def test_detect_passes_confidence_to_model(self):
        self._worker.confidence = 0.5
        self._worker.model.return_value = _make_mock_results(0)
        self._worker.detect(_make_frame())
        _, kwargs = self._worker.model.call_args
        self.assertEqual(kwargs['conf'], 0.5)


# ---------------------------------------------------------------------------
# QYoloOverlay
# ---------------------------------------------------------------------------

class TestQYoloOverlay(unittest.TestCase):

    def setUp(self):
        self._overlay = QYoloOverlay()

    def test_bounding_rect_is_nonempty(self):
        rect = self._overlay.boundingRect()
        self.assertGreater(rect.width(), 0)
        self.assertGreater(rect.height(), 0)

    def test_set_features_stores_data(self):
        features = _make_features(2)
        self._overlay.setFeatures(features)
        self.assertIs(self._overlay._features, features)

    def test_set_features_none_clears(self):
        self._overlay.setFeatures(_make_features())
        self._overlay.setFeatures(None)
        self.assertIsNone(self._overlay._features)


# ---------------------------------------------------------------------------
# QYoloWidget
# ---------------------------------------------------------------------------

class TestQYoloWidgetInit(unittest.TestCase):

    def test_initially_unchecked(self):
        w = _make_widget()
        self.assertFalse(w.isChecked())

    def test_no_source_by_default(self):
        w = _make_widget()
        self.assertIsNone(w.source)

    def test_initial_confidence_in_spinbox(self):
        w = _make_widget(confidence=0.5)
        self.assertAlmostEqual(w._confidenceSpinBox.value(), 0.5)


class TestQYoloWidgetSource(unittest.TestCase):

    def test_source_setter_connects_newframe(self):
        w = _make_widget()
        src = MockSource()
        w.source = src
        self.assertIs(w.source, src)

    def test_source_setter_none_after_source(self):
        w = _make_widget()
        w.source = MockSource()
        w.source = None
        self.assertIsNone(w.source)

    def test_source_replacement_disconnects_old(self):
        w = _make_widget()
        src1, src2 = MockSource(), MockSource()
        w.source = src1
        w.source = src2
        w.setChecked(True)
        spy = QtTest.QSignalSpy(w.newData)
        src1.newFrame.emit(_make_frame())
        QtWidgets.QApplication.processEvents()
        self.assertEqual(len(spy), 0)


class TestQYoloWidgetNewFrame(unittest.TestCase):

    def setUp(self):
        self._w = _make_widget()

    def test_new_frame_ignored_when_unchecked(self):
        spy = QtTest.QSignalSpy(self._w._detect)
        self._w._onNewFrame(_make_frame())
        self.assertEqual(len(spy), 0)

    def test_new_frame_dispatched_when_checked_and_ready(self):
        self._w.setChecked(True)
        spy = QtTest.QSignalSpy(self._w._detect)
        self._w._onNewFrame(_make_frame())
        self.assertEqual(len(spy), 1)

    def test_ready_flag_cleared_before_dispatch(self):
        self._w.setChecked(True)
        self._w._detect.disconnect(self._w._worker.detect)
        try:
            self._w._onNewFrame(_make_frame())
            self.assertFalse(self._w._ready)
        finally:
            self._w._detect.connect(self._w._worker.detect)

    def test_second_frame_dropped_while_busy(self):
        self._w.setChecked(True)
        self._w._ready = False
        spy = QtTest.QSignalSpy(self._w._detect)
        self._w._onNewFrame(_make_frame())
        self.assertEqual(len(spy), 0)


class TestQYoloWidgetNewData(unittest.TestCase):

    def setUp(self):
        self._w = _make_widget()
        self._w._ready = False

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
        features = _make_features(2)
        self._w._onNewData(features)
        self.assertIs(self._w._overlay._features, features)

    def test_none_features_clears_overlay(self):
        self._w._overlay.setFeatures(_make_features())
        self._w._onNewData(None)
        self.assertIsNone(self._w._overlay._features)


class TestQYoloWidgetAttachTo(unittest.TestCase):

    def test_attach_adds_overlay_to_view(self):
        w = _make_widget()
        screen = MockScreen()
        w.attachTo(screen)
        screen.addOverlay.assert_called_once_with(w._overlay)

    def test_detach_from_removes_overlay(self):
        w = _make_widget()
        screen = MockScreen()
        w.detachFrom(screen)
        screen.removeOverlay.assert_called_once_with(w._overlay)


class TestQYoloWidgetConfidence(unittest.TestCase):

    def test_set_confidence(self):
        w = _make_widget()
        w._setConfidence(0.6)
        self.assertAlmostEqual(w._worker.confidence, 0.6)


class TestQYoloWidgetCleanup(unittest.TestCase):

    def test_cleanup_disconnects_source(self):
        w = _make_widget()
        w.source = MockSource()
        w._cleanup()
        self.assertIsNone(w.source)

    def test_cleanup_stops_thread(self):
        w = _make_widget()
        w._thread.quit = MagicMock()
        w._thread.wait = MagicMock()
        w._cleanup()
        w._thread.quit.assert_called_once()
        w._thread.wait.assert_called_once()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
