'''Unit tests for YOLOFilter and QYOLOFilter.'''
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from qtpy import QtCore, QtWidgets, QtTest

import sys
import QVideo.filters.QYOLOFilter  # ensure module is loaded  # noqa: E402
from QVideo.filters.QYOLOFilter import YOLOFilter, QYOLOFilter  # noqa: E402

_mod = sys.modules['QVideo.filters.QYOLOFilter']


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((64, 64, 3), dtype=np.uint8)
_BOXES = np.array([[10., 10., 20., 20.], [30., 30., 50., 50.]], dtype=np.float32)
_ANNOTATED = np.ones((64, 64, 3), dtype=np.uint8)


def _make_mock_yolo():
    '''Return a mock YOLO class whose instances return canned detection results.'''
    mock_result = MagicMock()
    mock_result.boxes.xyxy.cpu().numpy.return_value = _BOXES
    mock_result.plot.return_value = _ANNOTATED
    mock_cls = MagicMock()
    mock_cls.return_value.return_value = [mock_result]
    return mock_cls


def make_filter(**kwargs) -> YOLOFilter:
    '''Create a YOLOFilter with mocked YOLO and synchronous threading.'''
    with patch.object(_mod, 'YOLO', _make_mock_yolo()), \
         patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return YOLOFilter(**kwargs)


# ---------------------------------------------------------------------------
# YOLOFilter init
# ---------------------------------------------------------------------------

class TestYOLOFilterInit(unittest.TestCase):

    def test_raises_import_error_when_yolo_missing(self):
        with patch.object(_mod, 'YOLO', None):
            with self.assertRaises(ImportError):
                YOLOFilter()

    def test_raises_file_not_found_for_bad_model(self):
        mock_cls = MagicMock(side_effect=FileNotFoundError)
        with patch.object(_mod, 'YOLO', mock_cls), \
             patch.object(QtCore.QThread, 'start'), \
             patch.object(QtCore.QObject, 'moveToThread'):
            with self.assertRaises(FileNotFoundError):
                YOLOFilter('nonexistent.pt')

    def test_default_passthrough_is_false(self):
        f = make_filter()
        self.assertFalse(f.passthrough)

    def test_passthrough_can_be_set_at_init(self):
        f = make_filter(passthrough=True)
        self.assertTrue(f.passthrough)


# ---------------------------------------------------------------------------
# YOLOFilter passthrough property
# ---------------------------------------------------------------------------

class TestYOLOFilterPassthrough(unittest.TestCase):

    def setUp(self):
        self.f = make_filter()

    def test_setter_stores_bool(self):
        self.f.passthrough = True
        self.assertTrue(self.f.passthrough)

    def test_setter_coerces_to_bool(self):
        self.f.passthrough = 1
        self.assertIs(self.f.passthrough, True)


# ---------------------------------------------------------------------------
# YOLOFilter.process (the heavy computation, now testable directly)
# ---------------------------------------------------------------------------

class TestYOLOFilterProcess(unittest.TestCase):

    def setUp(self):
        self.f = make_filter()

    def test_process_calls_model_with_image(self):
        self.f.process(_FRAME)
        self.f.model.assert_called_once_with(_FRAME, verbose=False)

    def test_process_emits_features_ready(self):
        spy = QtTest.QSignalSpy(self.f.featuresReady)
        self.f.process(_FRAME)
        self.assertEqual(len(spy), 1)

    def test_process_features_ready_contains_boxes(self):
        spy = QtTest.QSignalSpy(self.f.featuresReady)
        self.f.process(_FRAME)
        np.testing.assert_array_equal(spy[0][0], _BOXES)

    def test_process_returns_annotated_when_not_passthrough(self):
        self.f.passthrough = False
        result = self.f.process(_FRAME)
        np.testing.assert_array_equal(result, _ANNOTATED)

    def test_process_returns_original_when_passthrough(self):
        self.f.passthrough = True
        result = self.f.process(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)


# ---------------------------------------------------------------------------
# QYOLOFilter
# ---------------------------------------------------------------------------

class TestQYOLOFilter(unittest.TestCase):

    def setUp(self):
        with patch.object(_mod, 'YOLO', _make_mock_yolo()), \
             patch.object(QtCore.QThread, 'start'), \
             patch.object(QtCore.QObject, 'moveToThread'):
            self.widget = QYOLOFilter(parent=None)

    def test_is_qvideofilter(self):
        from QVideo.lib.QVideoFilter import QVideoFilter
        self.assertIsInstance(self.widget, QVideoFilter)

    def test_filter_is_yolofilter(self):
        self.assertIsInstance(self.widget.filter, YOLOFilter)

    def test_title(self):
        self.assertEqual(self.widget.title(), 'YOLO Filter')

    def test_initially_unchecked(self):
        self.assertFalse(self.widget.isChecked())

    def test_has_passthrough_checkbox(self):
        self.assertIsNotNone(self.widget._checkbox)

    def test_set_passthrough_updates_filter(self):
        self.widget._setPassthrough(2)  # Qt.Checked == 2
        self.assertTrue(self.widget.filter.passthrough)

    def test_unset_passthrough_updates_filter(self):
        self.widget._setPassthrough(0)
        self.assertFalse(self.widget.filter.passthrough)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        result = self.widget(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)

    def test_call_when_checked_runs_model(self):
        self.widget.setChecked(True)
        self.widget(_FRAME)
        self.widget.filter.model.assert_called_once_with(_FRAME, verbose=False)


if __name__ == '__main__':
    unittest.main()
