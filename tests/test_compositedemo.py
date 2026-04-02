'''Unit tests for demos.compositedemo.'''
import unittest
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
import QVideo.overlays.trackpy as _trackpy_mod
from QVideo.QCamcorder import QCamcorder
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.compositedemo import CompositeDemo
from QVideo.overlays.trackpy import QTrackpyWidget, _TrackpyWorker


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_demo():
    with patch.object(_trackpy_mod, 'tp', MagicMock()), \
         patch.object(_TrackpyWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'):
        return CompositeDemo(QNoiseTree())


class TestCompositeDemoInit(unittest.TestCase):

    def test_creates_successfully(self):
        widget = make_demo()
        self.assertIsInstance(widget, CompositeDemo)

    def test_is_subclass_of_qcamcorder(self):
        widget = make_demo()
        self.assertIsInstance(widget, QCamcorder)

    def test_trackpy_attribute_is_qtrackpywidget(self):
        widget = make_demo()
        self.assertIsInstance(widget.trackpy, QTrackpyWidget)

    def test_trackpy_source_connected_to_camera_source(self):
        tree = QNoiseTree()
        with patch.object(_trackpy_mod, 'tp', MagicMock()), \
             patch.object(_TrackpyWorker, 'moveToThread'), \
             patch.object(QtCore.QThread, 'start'):
            widget = CompositeDemo(tree)
        self.assertIs(widget.trackpy.source, tree.source)

    def test_composite_check_is_qcheckbox(self):
        widget = make_demo()
        self.assertIsInstance(widget._compositeCheck, QtWidgets.QCheckBox)

    def test_composite_check_label(self):
        widget = make_demo()
        self.assertEqual(widget._compositeCheck.text(), 'Composite')

    def test_controls_contains_trackpy_widget(self):
        widget = make_demo()
        layout = widget.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.trackpy, items)

    def test_controls_contains_composite_check(self):
        widget = make_demo()
        layout = widget.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget._compositeCheck, items)

    def test_overlay_added_to_screen(self):
        widget = make_demo()
        self.assertIn(widget.trackpy.overlay, widget.screen._overlays)


class TestCompositeDemoToggle(unittest.TestCase):

    def setUp(self):
        self.widget = make_demo()

    def test_composite_off_by_default(self):
        self.assertFalse(self.widget._compositeCheck.isChecked())

    def test_toggle_on_sets_screen_composite(self):
        self.widget._onCompositeToggled(True)
        self.assertTrue(self.widget.screen.composite)

    def test_toggle_on_sets_dvr_source_to_screen(self):
        self.widget._onCompositeToggled(True)
        self.assertIs(self.widget.dvr.source, self.widget.screen)

    def test_toggle_off_clears_screen_composite(self):
        self.widget._onCompositeToggled(True)
        self.widget._onCompositeToggled(False)
        self.assertFalse(self.widget.screen.composite)

    def test_toggle_off_restores_dvr_source_to_camera(self):
        self.widget._onCompositeToggled(True)
        self.widget._onCompositeToggled(False)
        self.assertIs(self.widget.dvr.source, self.widget.source)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
