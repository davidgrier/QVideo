'''Unit tests for demos.filterrackdemo.'''
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QSignalSpy
from QVideo.QCamcorder import QCamcorder
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.filterrackdemo import FilterRackDemo, _FilteredSource
from QVideo.lib import QFilterRack
from QVideo.filters import QSmoothingFilter, QThresholdFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((4, 4), dtype=np.uint8)


def make_demo() -> FilterRackDemo:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return FilterRackDemo(QNoiseTree())


class TestFilteredSource(unittest.TestCase):

    def _make_source(self, fps=30.0):
        source = MagicMock()
        source.fps = fps
        return source

    def test_fps_delegates_to_source(self):
        source = self._make_source(fps=25.0)
        rack = MagicMock(return_value=_FRAME)
        fs = _FilteredSource(source, rack)
        self.assertEqual(fs.fps, 25.0)

    def test_fps_none_when_source_fps_is_none(self):
        source = self._make_source(fps=None)
        rack = MagicMock(return_value=_FRAME)
        fs = _FilteredSource(source, rack)
        self.assertIsNone(fs.fps)

    def test_process_calls_rack(self):
        source = self._make_source()
        rack = MagicMock(return_value=_FRAME)
        fs = _FilteredSource(source, rack)
        fs._process(_FRAME)
        rack.assert_called_once_with(_FRAME)

    def test_process_emits_new_frame(self):
        source = self._make_source()
        rack = MagicMock(return_value=_FRAME)
        fs = _FilteredSource(source, rack)
        spy = QSignalSpy(fs.newFrame)
        fs._process(_FRAME)
        self.assertEqual(len(spy), 1)

    def test_process_emits_filtered_result(self):
        source = self._make_source()
        filtered = np.ones((4, 4), dtype=np.uint8) * 42
        rack = MagicMock(return_value=filtered)
        fs = _FilteredSource(source, rack)
        spy = QSignalSpy(fs.newFrame)
        fs._process(_FRAME)
        np.testing.assert_array_equal(spy[0][0], filtered)


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

    def test_screen_filter_is_rack(self):
        widget = make_demo()
        self.assertIs(widget.screen.filter, widget.rack)

    def test_has_filtered_source(self):
        widget = make_demo()
        self.assertIsInstance(widget._filteredSource, _FilteredSource)

    def test_filtered_source_uses_rack(self):
        widget = make_demo()
        self.assertIs(widget._filteredSource._rack, widget.rack)

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


class TestFilterRackDemoModes(unittest.TestCase):

    def setUp(self):
        self.widget = make_demo()

    def test_raw_mode_sets_dvr_source_to_camera(self):
        self.widget._onModeToggled(self.widget._modeRaw, True)
        self.assertIs(self.widget.dvr.source, self.widget.source)

    def test_filtered_mode_sets_dvr_source_to_filtered_source(self):
        self.widget._onModeToggled(self.widget._modeFiltered, True)
        self.assertIs(self.widget.dvr.source, self.widget._filteredSource)

    def test_display_mode_sets_dvr_source_to_screen(self):
        self.widget._onModeToggled(self.widget._modeDisplay, True)
        self.assertIs(self.widget.dvr.source, self.widget.screen)

    def test_deselect_does_not_change_source(self):
        self.widget._onModeToggled(self.widget._modeFiltered, True)
        self.widget._onModeToggled(self.widget._modeFiltered, False)
        self.assertIs(self.widget.dvr.source, self.widget._filteredSource)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
