'''Unit tests for demos.filterrackdemo.'''
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QSignalSpy
from QVideo.QCamcorder import QCamcorder
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.filterrackdemo import FilterRackDemo
from QVideo.dvr import QSourceSelector
from QVideo.lib import QFilterRack, QFilterPipeline
from QVideo.filters import QSmoothingFilter, QThresholdFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((4, 4), dtype=np.uint8)


def make_demo() -> FilterRackDemo:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return FilterRackDemo(QNoiseTree())


class TestFilterRackDemoInit(unittest.TestCase):

    def test_is_qcamcorder(self):
        widget = make_demo()
        self.assertIsInstance(widget, QCamcorder)

    def test_rack_is_qfilterrack(self):
        widget = make_demo()
        self.assertIsInstance(widget.rack, QFilterRack)

    def test_rack_has_blur_filter(self):
        widget = make_demo()
        self.assertTrue(
            any(isinstance(f, QSmoothingFilter) for f in widget.rack.filters))

    def test_rack_has_threshold_filter(self):
        widget = make_demo()
        self.assertTrue(
            any(isinstance(f, QThresholdFilter) for f in widget.rack.filters))

    def test_pipeline_is_a_filter_pipeline(self):
        widget = make_demo()
        self.assertIsInstance(widget.rack.pipeline, QFilterPipeline)

    def test_pipeline_runs_the_rack(self):
        widget = make_demo()
        self.assertIs(widget.rack.pipeline.rack, widget.rack)

    def test_pipeline_reads_the_camera_source(self):
        widget = make_demo()
        self.assertIs(widget.rack.pipeline.source, widget.source)

    def test_screen_displays_the_pipeline(self):
        widget = make_demo()
        self.assertIs(widget.screen.source, widget.rack.pipeline)

    def test_rack_is_not_also_applied_by_the_screen(self):
        '''One filtered stream feeds display and recording; the screen's
        own filter bank stays empty so stateful filters see each frame once.'''
        widget = make_demo()
        self.assertFalse(hasattr(widget.screen, 'filter'))

    def test_dvr_source_is_camera_source_by_default(self):
        widget = make_demo()
        self.assertIs(widget.dvr.source, widget.source)

    def test_selector_offers_the_three_streams(self):
        widget = make_demo()
        self.assertIsInstance(widget.selector, QSourceSelector)
        self.assertEqual([b.text() for b in widget.selector._sources],
                         ['Raw', 'Filtered', 'Display'])

    def test_raw_is_selected_by_default(self):
        widget = make_demo()
        self.assertEqual(widget.selector.sourceName, 'Raw')

    def test_selector_in_controls(self):
        widget = make_demo()
        layout = widget.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.selector, items)

    def test_rack_in_controls(self):
        widget = make_demo()
        layout = widget.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.rack, items)


class TestFilterRackDemoDvrPlayback(unittest.TestCase):
    '''During playback the pipeline filters the DVR player instead of the
    camera, so playback frames are filtered exactly once.'''

    def setUp(self):
        self.widget = make_demo()

    def test_playback_points_the_pipeline_at_the_player(self):
        self.widget.dvrPlayback(True)
        self.assertIs(self.widget.rack.pipeline.source,
                      self.widget.dvr.playback.source)

    def test_playback_keeps_the_screen_on_the_pipeline(self):
        self.widget.dvrPlayback(True)
        self.assertIs(self.widget.screen.source, self.widget.rack.pipeline)

    def test_end_of_playback_restores_the_camera(self):
        self.widget.dvrPlayback(True)
        self.widget.dvrPlayback(False)
        self.assertIs(self.widget.rack.source, self.widget.source)

    def test_camera_controls_follow_playback(self):
        self.widget.dvrPlayback(True)
        self.assertFalse(self.widget.cameraWidget.isEnabled())
        self.widget.dvrPlayback(False)
        self.assertTrue(self.widget.cameraWidget.isEnabled())


class TestFilterRackDemoModes(unittest.TestCase):

    def setUp(self):
        self.widget = make_demo()

    def test_raw_mode_sets_dvr_source_to_camera(self):
        self.widget.selector.sourceName = 'Filtered'
        self.widget.selector.sourceName = 'Raw'
        self.assertIs(self.widget.dvr.source, self.widget.source)

    def test_filtered_mode_sets_dvr_source_to_pipeline(self):
        self.widget.selector.sourceName = 'Filtered'
        self.assertIs(self.widget.dvr.source, self.widget.rack.pipeline)

    def test_display_mode_sets_dvr_source_to_screen(self):
        self.widget.selector.sourceName = 'Display'
        self.assertIs(self.widget.dvr.source, self.widget.screen)

    def test_the_choice_is_locked_while_recording(self):
        self.widget.dvr.recording.emit(True)
        self.assertFalse(self.widget.selector.isEnabled())
        self.widget.dvr.recording.emit(False)
        self.assertTrue(self.widget.selector.isEnabled())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
