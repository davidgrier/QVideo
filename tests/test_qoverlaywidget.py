'''Unit tests for QOverlayWidget.'''
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
from QVideo.tests.signals import record
from QVideo.lib import QOverlayWidget


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Worker(QtCore.QObject):
    '''The smallest worker: report the mean of the frame.'''

    newData = QtCore.Signal(object)

    @QtCore.Slot(np.ndarray)
    def process(self, image):
        self.newData.emit(float(image.mean()))


class _Overlay(QtWidgets.QGraphicsRectItem):
    '''The smallest overlay: remember the last result.'''

    features = None

    def setFeatures(self, features):
        self.features = features


class _Widget(QOverlayWidget):

    def __init__(self, parent=None):
        super().__init__('Test', _Overlay(), _Worker(), parent)

    def _setupUi(self):
        super()._setupUi()
        self._box = QtWidgets.QSpinBox()
        self._layout.addRow('Box', self._box)


class MockSource(QtCore.QObject):
    newFrame = QtCore.Signal(np.ndarray)


def make_widget() -> _Widget:
    '''A widget whose worker stays in the main thread, so that a frame is
    processed where it is handed over, and no thread is started.'''
    with patch.object(_Worker, 'moveToThread'), \
            patch.object(QtCore.QThread, 'start'):
        return _Widget()


def frame(value=10):
    return np.full((4, 4), value, dtype=np.uint8)


class TestInit(unittest.TestCase):

    def test_initially_unchecked(self):
        self.assertFalse(make_widget().isChecked())

    def test_no_source_by_default(self):
        self.assertIsNone(make_widget().source)

    def test_the_title_is_shown(self):
        self.assertEqual(make_widget().title(), 'Test')

    def test_the_overlay_is_the_one_that_was_given(self):
        w = make_widget()
        self.assertIs(w.overlay, w._overlay)
        self.assertIsInstance(w.overlay, _Overlay)

    def test_a_subclass_adds_controls_to_the_form_layout(self):
        w = make_widget()
        self.assertIsInstance(w._layout, QtWidgets.QFormLayout)
        self.assertIsInstance(w._box, QtWidgets.QSpinBox)

    def test_the_check_box_shows_and_hides_the_overlay(self):
        w = make_widget()
        w.setChecked(True)
        self.assertTrue(w.overlay.isVisible())
        w.setChecked(False)
        self.assertFalse(w.overlay.isVisible())


class TestSource(unittest.TestCase):

    def test_source_setter_connects_newframe(self):
        w = make_widget()
        src = MockSource()
        w.source = src
        self.assertIs(w.source, src)
        w.setChecked(True)
        src.newFrame.emit(frame())
        QtWidgets.QApplication.processEvents()
        self.assertIsNotNone(w.overlay.features)

    def test_source_setter_none_after_source(self):
        w = make_widget()
        w.source = MockSource()
        w.source = None
        self.assertIsNone(w.source)

    def test_source_replacement_disconnects_old(self):
        w = make_widget()
        src1, src2 = MockSource(), MockSource()
        w.source = src1
        w.source = src2
        spy = record(w.newData)
        w.setChecked(True)
        src1.newFrame.emit(frame())
        QtWidgets.QApplication.processEvents()
        self.assertEqual(len(spy), 0)


class TestNewFrame(unittest.TestCase):

    def test_new_frame_ignored_when_unchecked(self):
        w = make_widget()
        spy = record(w._process)
        w._onNewFrame(frame())
        self.assertEqual(len(spy), 0)

    def test_new_frame_dispatched_when_checked_and_ready(self):
        w = make_widget()
        w.setChecked(True)
        spy = record(w._process)
        w._onNewFrame(frame())
        self.assertEqual(len(spy), 1)

    def test_the_worker_gets_the_frame(self):
        w = make_widget()
        w.setChecked(True)
        w._onNewFrame(frame(30))
        self.assertEqual(w.overlay.features, 30.)

    def test_ready_flag_cleared_before_dispatch(self):
        w = make_widget()
        w.setChecked(True)
        w._process.disconnect(w._worker.process)  # keep the frame in flight
        w._onNewFrame(frame())
        self.assertFalse(w._ready)

    def test_second_frame_dropped_while_busy(self):
        w = make_widget()
        w.setChecked(True)
        w._ready = False  # the worker is still running
        spy = record(w._process)
        w._onNewFrame(frame())
        self.assertEqual(len(spy), 0)


class TestNewData(unittest.TestCase):

    def setUp(self):
        self.w = make_widget()
        self.w._ready = False  # a request is in flight

    def test_ready_flag_restored(self):
        self.w._onNewData(1.)
        self.assertTrue(self.w._ready)

    def test_new_data_signal_emitted(self):
        spy = record(self.w.newData)
        self.w._onNewData(2.)
        self.assertEqual(spy, [(2.,)])

    def test_the_overlay_gets_the_result(self):
        self.w._onNewData(3.)
        self.assertEqual(self.w.overlay.features, 3.)

    def test_none_is_passed_on(self):
        self.w._onNewData(3.)
        self.w._onNewData(None)
        self.assertIsNone(self.w.overlay.features)


class TestCleanup(unittest.TestCase):

    def test_stop_disconnects_source(self):
        w = make_widget()
        w.source = MockSource()
        w.stop()
        self.assertIsNone(w.source)

    def test_stop_stops_thread(self):
        w = make_widget()
        thread = w._thread
        thread.quit = MagicMock()
        thread.wait = MagicMock()
        w.stop()
        thread.quit.assert_called_once()
        thread.wait.assert_called_once()

    def test_stop_twice_is_safe(self):
        w = make_widget()
        w.stop()
        w.stop()
        self.assertFalse(w._thread.isRunning())

    def test_closing_the_widget_stops_it(self):
        w = make_widget()
        w.source = MockSource()
        w.close()
        self.assertIsNone(w.source)

    def test_deleting_the_widget_stops_the_thread(self):
        w = make_widget()
        thread = w._thread
        thread.quit = MagicMock()
        thread.wait = MagicMock()
        w.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(
            None, QtCore.QEvent.Type.DeferredDelete)
        thread.quit.assert_called_once()
        thread.wait.assert_called_once()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
