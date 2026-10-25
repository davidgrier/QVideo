'''Unit tests for demos.filterrackdemo.'''
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QSignalSpy
from QVideo.QCamcorder import QCamcorder
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.filterrackdemo import FilterRackDemo
from QVideo.lib import QFilterRack, QFilterStack
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

    def test_stack_is_a_filter_stack(self):
        widget = make_demo()
        self.assertIsInstance(widget.stack, QFilterStack)

    def test_stack_runs_the_rack(self):
        widget = make_demo()
        self.assertIs(widget.stack.rack, widget.rack)

    def test_stack_reads_the_camera_source(self):
        widget = make_demo()
        self.assertIs(widget.stack.source, widget.source)

    def test_screen_displays_the_stack(self):
        widget = make_demo()
        self.assertIs(widget.screen.source, widget.stack)

    def test_rack_is_not_also_applied_by_the_screen(self):
        '''One filtered stream feeds display and recording; the screen's
        own filter bank stays empty so stateful filters see each frame once.'''
        widget = make_demo()
        self.assertFalse(hasattr(widget.screen, 'filter'))

    def test_dvr_source_is_camera_source_by_default(self):
        widget = make_demo()
        self.assertIs(widget.dvr.source, widget.source)

    def test_mode_raw_is_radio_button(self):
        widget = make_demo()
        self.assertIsInstance(widget._modeRaw, QtWidgets.QRadioButton)

    def test_mode_filtered_is_radio_button(self):
        widget = make_demo()
        self.assertIsInstance(widget._modeFiltered, QtWidgets.QRadioButton)

    def test_mode_display_is_radio_button(self):
        widget = make_demo()
        self.assertIsInstance(widget._modeDisplay, QtWidgets.QRadioButton)

    def test_mode_raw_checked_by_default(self):
        widget = make_demo()
        self.assertTrue(widget._modeRaw.isChecked())

    def test_mode_box_in_controls(self):
        widget = make_demo()
        layout = widget.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget._modeBox, items)

    def test_rack_in_controls(self):
        widget = make_demo()
        layout = widget.controls.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.rack, items)


class TestFilterRackDemoDvrPlayback(unittest.TestCase):
    '''During playback the stack filters the DVR player instead of the
    camera, so playback frames are filtered exactly once.'''

    def setUp(self):
        self.widget = make_demo()

    def test_playback_points_the_stack_at_the_player(self):
        self.widget.dvrPlayback(True)
        self.assertIs(self.widget.stack.source, self.widget.dvr.player)

    def test_playback_keeps_the_screen_on_the_stack(self):
        self.widget.dvrPlayback(True)
        self.assertIs(self.widget.screen.source, self.widget.stack)

    def test_end_of_playback_restores_the_camera(self):
        self.widget.dvrPlayback(True)
        self.widget.dvrPlayback(False)
        self.assertIs(self.widget.stack.source, self.widget.source)

    def test_camera_controls_follow_playback(self):
        self.widget.dvrPlayback(True)
        self.assertFalse(self.widget.cameraWidget.isEnabled())
        self.widget.dvrPlayback(False)
        self.assertTrue(self.widget.cameraWidget.isEnabled())


class TestFilterRackDemoModes(unittest.TestCase):

    def setUp(self):
        self.widget = make_demo()

    def test_raw_mode_sets_dvr_source_to_camera(self):
        self.widget._onModeToggled(self.widget._modeRaw, True)
        self.assertIs(self.widget.dvr.source, self.widget.source)

    def test_filtered_mode_sets_dvr_source_to_stack(self):
        self.widget._onModeToggled(self.widget._modeFiltered, True)
        self.assertIs(self.widget.dvr.source, self.widget.stack)

    def test_display_mode_sets_dvr_source_to_screen(self):
        self.widget._onModeToggled(self.widget._modeDisplay, True)
        self.assertIs(self.widget.dvr.source, self.widget.screen)

    def test_deselect_does_not_change_source(self):
        self.widget._onModeToggled(self.widget._modeFiltered, True)
        self.widget._onModeToggled(self.widget._modeFiltered, False)
        self.assertIs(self.widget.dvr.source, self.widget.stack)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
