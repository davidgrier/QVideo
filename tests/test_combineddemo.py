'''Unit tests for demos.combineddemo.'''
import unittest
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
import QVideo.overlays.trackpy as _trackpy_mod
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.combineddemo import CombinedDemo
from QVideo.demos.filterrackdemo import FilterRackDemo
from QVideo.lib import QFilterPipeline
from QVideo.overlays.trackpy import QTrackpyWidget, _TrackpyWorker


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_demo() -> CombinedDemo:
    with patch.object(_trackpy_mod, 'tp', MagicMock()), \
         patch.object(_TrackpyWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return CombinedDemo(QNoiseTree())


class TestStructure(unittest.TestCase):

    def test_extends_the_filter_rack_demo(self):
        self.assertIsInstance(make_demo(), FilterRackDemo)

    def test_the_overlay_widget_is_present(self):
        self.assertIsInstance(make_demo().trackpy, QTrackpyWidget)

    def test_particles_are_located_in_the_filtered_stream(self):
        demo = make_demo()
        self.assertIsInstance(demo.rack.pipeline, QFilterPipeline)
        self.assertIs(demo.trackpy.source, demo.rack.pipeline)

    def test_the_screen_shows_the_filtered_stream(self):
        demo = make_demo()
        self.assertIs(demo.screen.source, demo.rack.pipeline)

    def test_the_overlay_is_drawn_on_the_screen(self):
        demo = make_demo()
        self.assertIn(demo.trackpy.overlay, demo.screen._overlays)

    def test_the_overlay_panel_is_in_the_controls(self):
        demo = make_demo()
        layout = demo.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(demo.trackpy, items)

    def test_composite_is_a_fourth_recording_mode(self):
        demo = make_demo()
        self.assertEqual([b.text() for b in demo.selector._sources],
                         ['Raw', 'Filtered', 'Display', 'Composite'])


class TestModes(unittest.TestCase):

    def test_raw_is_the_default_and_records_the_camera(self):
        demo = make_demo()
        self.assertIs(demo.dvr.source, demo.source)
        self.assertFalse(demo.screen.composite)

    def test_composite_records_the_rendered_scene(self):
        demo = make_demo()
        demo.selector.sourceName = 'Composite'
        self.assertIs(demo.dvr.source, demo.screen)
        self.assertTrue(demo.screen.composite)

    def test_filtered_records_the_pipeline_without_the_overlay(self):
        demo = make_demo()
        demo.selector.sourceName = 'Composite'
        demo.selector.sourceName = 'Filtered'
        self.assertIs(demo.dvr.source, demo.rack.pipeline)
        self.assertFalse(demo.screen.composite)

    def test_display_records_the_screen_without_the_overlay(self):
        demo = make_demo()
        demo.selector.sourceName = 'Composite'
        demo.selector.sourceName = 'Display'
        self.assertIs(demo.dvr.source, demo.screen)
        self.assertFalse(demo.screen.composite)

    def test_leaving_composite_for_raw_records_the_camera(self):
        demo = make_demo()
        demo.selector.sourceName = 'Composite'
        demo.selector.sourceName = 'Raw'
        self.assertIs(demo.dvr.source, demo.source)
        self.assertFalse(demo.screen.composite)


if __name__ == '__main__':
    unittest.main()
