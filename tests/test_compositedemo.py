'''Unit tests for demos.compositedemo.'''
import unittest
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
import QVideo.overlays.trackpy as _trackpy_mod
from QVideo.QCamcorder import QCamcorder
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.dvr import QSourceSelector
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

    def test_the_selector_offers_raw_and_composite(self):
        widget = make_demo()
        self.assertIsInstance(widget.selector, QSourceSelector)
        self.assertEqual([b.text() for b in widget.selector._sources],
                         ['Raw', 'Composite'])

    def test_controls_contains_trackpy_widget(self):
        widget = make_demo()
        layout = widget.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.trackpy, items)

    def test_controls_contains_the_selector(self):
        widget = make_demo()
        layout = widget.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.selector, items)

    def test_overlay_added_to_screen(self):
        widget = make_demo()
        self.assertIn(widget.trackpy.overlay, widget.screen._overlays)


class TestCompositeDemoToggle(unittest.TestCase):

    def setUp(self):
        self.widget = make_demo()

    def test_raw_is_selected_by_default(self):
        self.assertEqual(self.widget.selector.sourceName, 'Raw')
        self.assertFalse(self.widget.screen.composite)

    def test_composite_sets_screen_composite(self):
        self.widget.selector.sourceName = 'Composite'
        self.assertTrue(self.widget.screen.composite)

    def test_composite_sets_dvr_source_to_screen(self):
        self.widget.selector.sourceName = 'Composite'
        self.assertIs(self.widget.dvr.source, self.widget.screen)

    def test_raw_clears_screen_composite(self):
        self.widget.selector.sourceName = 'Composite'
        self.widget.selector.sourceName = 'Raw'
        self.assertFalse(self.widget.screen.composite)

    def test_raw_restores_dvr_source_to_camera(self):
        self.widget.selector.sourceName = 'Composite'
        self.widget.selector.sourceName = 'Raw'
        self.assertIs(self.widget.dvr.source, self.widget.source)

    def test_the_selector_is_locked_while_recording(self):
        self.widget.dvr.recording.emit(True)
        self.assertFalse(self.widget.selector.isEnabled())
        self.widget.dvr.recording.emit(False)
        self.assertTrue(self.widget.selector.isEnabled())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
