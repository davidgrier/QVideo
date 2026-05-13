'''Unit tests for QCamcorder.'''
import unittest
import numpy as np
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.QCamcorder import QCamcorder
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.lib.QSnapshot import QSnapshot


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class MockSource(QtCore.QObject):
    '''Minimal QVideoSource stand-in with the signals QVideoScreen expects.'''
    newFrame = QtCore.Signal(np.ndarray)
    shapeChanged = QtCore.Signal(QtCore.QSize)

    def __init__(self):
        super().__init__()
        self.shape = QtCore.QSize(320, 240)


def make_camcorder():
    return QCamcorder(QNoiseTree())


class TestQCamcorderInit(unittest.TestCase):

    def test_creates_successfully(self):
        widget = make_camcorder()
        self.assertIsInstance(widget, QCamcorder)

    def test_screen_source_connected_to_camera_source(self):
        tree = QNoiseTree()
        widget = QCamcorder(tree)
        self.assertIs(widget.screen.source, tree.source)

    def test_dvr_source_connected_to_camera_source(self):
        tree = QNoiseTree()
        widget = QCamcorder(tree)
        self.assertIs(widget.dvr.source, tree.source)

    def test_camera_widget_added_to_controls(self):
        tree = QNoiseTree()
        widget = QCamcorder(tree)
        layout = widget.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(tree, items)

    def test_source_property_returns_camera_widget_source(self):
        tree = QNoiseTree()
        widget = QCamcorder(tree)
        self.assertIs(widget.source, tree.source)

    def test_snapshot_is_qsnapshot(self):
        self.assertIsInstance(make_camcorder()._snapshot, QSnapshot)

    def test_screen_newframe_connected_to_snapshot(self):
        widget = make_camcorder()
        frame = np.zeros((4, 6, 3), dtype=np.uint8)
        widget.screen.newFrame.emit(frame)
        self.assertIs(widget._snapshot._frame, frame)


class TestQCamcorderCloseEvent(unittest.TestCase):

    def test_close_event_stops_camera_source(self):
        tree = QNoiseTree()
        widget = QCamcorder(tree)
        tree.start()
        event = QtGui.QCloseEvent()
        widget.closeEvent(event)
        self.assertFalse(tree.source.isRunning())

    def test_close_event_safe_when_not_running(self):
        widget = make_camcorder()
        event = QtGui.QCloseEvent()
        widget.closeEvent(event)  # should not raise


class TestQCamcorderDvrPlayback(unittest.TestCase):

    def setUp(self):
        self.widget = make_camcorder()
        self.mock_player = MockSource()
        self.widget.dvr._player = self.mock_player

    def test_dvr_playback_true_disables_camera_widget(self):
        self.widget.dvrPlayback(True)
        self.assertFalse(self.widget.cameraWidget.isEnabled())

    def test_dvr_playback_true_sets_screen_source_to_player(self):
        self.widget.dvrPlayback(True)
        self.assertIs(self.widget.screen.source, self.mock_player)

    def test_dvr_playback_false_enables_camera_widget(self):
        self.widget.dvrPlayback(True)
        self.widget.dvrPlayback(False)
        self.assertTrue(self.widget.cameraWidget.isEnabled())

    def test_dvr_playback_false_restores_screen_source(self):
        self.widget.dvrPlayback(True)
        self.widget.dvrPlayback(False)
        self.assertIs(self.widget.screen.source, self.widget.source)

    def test_dvr_playback_false_without_prior_true_does_not_raise(self):
        self.widget.dvr._player = None
        self.widget.dvrPlayback(False)  # should not raise


if __name__ == '__main__':
    unittest.main()
