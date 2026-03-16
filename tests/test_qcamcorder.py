'''Unit tests for QCamcorder.'''
import unittest
from pyqtgraph.Qt import QtWidgets
from QVideo.QCamcorder import QCamcorder
from QVideo.cameras.Noise.QNoiseTree import QNoiseTree


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


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


class TestQCamcorderDvrPlayback(unittest.TestCase):

    def test_dvr_playback_true_disables_camera_widget(self):
        widget = make_camcorder()
        widget.dvrPlayback(True)
        self.assertFalse(widget.cameraWidget.isEnabled())

    def test_dvr_playback_true_disconnects_source_from_screen(self):
        widget = make_camcorder()
        widget.dvrPlayback(True)
        # source.newFrame should be disconnected; trying to disconnect again raises
        with self.assertRaises(Exception):
            widget.source.newFrame.disconnect(widget.screen.setImage)

    def test_dvr_playback_true_connects_dvr_to_screen(self):
        widget = make_camcorder()
        widget.dvrPlayback(True)
        # dvr.newFrame should now be connected; disconnect should succeed
        widget.dvr.newFrame.disconnect(widget.screen.setImage)

    def test_dvr_playback_false_enables_camera_widget(self):
        widget = make_camcorder()
        widget.dvrPlayback(True)
        widget.dvrPlayback(False)
        self.assertTrue(widget.cameraWidget.isEnabled())

    def test_dvr_playback_false_reconnects_source_to_screen(self):
        widget = make_camcorder()
        widget.dvrPlayback(True)
        widget.dvrPlayback(False)
        # source.newFrame should be reconnected; disconnect should succeed
        widget.source.newFrame.disconnect(widget.screen.setImage)

    def test_dvr_playback_false_disconnects_dvr_from_screen(self):
        widget = make_camcorder()
        widget.dvrPlayback(True)
        widget.dvrPlayback(False)
        # dvr.newFrame should be disconnected; trying to disconnect again raises
        with self.assertRaises(Exception):
            widget.dvr.newFrame.disconnect(widget.screen.setImage)


if __name__ == '__main__':
    unittest.main()
