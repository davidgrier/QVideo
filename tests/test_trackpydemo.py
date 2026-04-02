'''Unit tests for demos.trackpydemo.'''
import unittest
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
import QVideo.overlays.trackpy as _trackpy_mod
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo
from QVideo.demos.trackpydemo import TrackpyDemo
from QVideo.overlays.trackpy import QTrackpyWidget, _TrackpyWorker


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_demo():
    with patch.object(_trackpy_mod, 'tp', MagicMock()), \
         patch.object(_TrackpyWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'):
        return TrackpyDemo(QNoiseTree())


class TestTrackpyDemoInit(unittest.TestCase):

    def test_creates_successfully(self):
        widget = make_demo()
        self.assertIsInstance(widget, TrackpyDemo)

    def test_is_subclass_of_demo(self):
        widget = make_demo()
        self.assertIsInstance(widget, Demo)

    def test_trackpy_attribute_is_qtrackpywidget(self):
        widget = make_demo()
        self.assertIsInstance(widget.trackpy, QTrackpyWidget)

    def test_trackpy_source_connected_to_screen_source(self):
        widget = make_demo()
        self.assertIs(widget.trackpy.source, widget.screen.source)

    def test_controls_contains_trackpy_widget(self):
        widget = make_demo()
        items = [widget._controls.itemAt(i).widget()
                 for i in range(widget._controls.count())]
        self.assertIn(widget.trackpy, items)

    def test_overlay_added_to_screen(self):
        widget = make_demo()
        self.assertIn(widget.trackpy.overlay, widget.screen._overlays)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
