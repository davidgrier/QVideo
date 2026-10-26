'''Unit tests for demos.filterdemo.'''
import unittest
from qtpy import QtCore, QtWidgets
from QVideo.lib import QFilterRack, QFilterPipeline, QVideoScreen
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo
from QVideo.demos.filterdemo import FilterDemo
from QVideo.filters import QRGBFilter, QSmoothingFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

FILTERS = ['Color Channel', 'Smoothing']


class TestFilterDemo(unittest.TestCase):

    def _make_demo(self, filters=None, tree=None):
        widget = FilterDemo(tree or QNoiseTree(),
                            FILTERS if filters is None else filters)
        self.addCleanup(widget.rack.pipeline.stop)
        return widget

    def test_creates_successfully(self):
        self.assertIsInstance(self._make_demo(), FilterDemo)

    def test_is_subclass_of_demo(self):
        self.assertIsInstance(self._make_demo(), Demo)

    def test_screen_attribute_is_qvideoscreen(self):
        self.assertIsInstance(self._make_demo().screen, QVideoScreen)

    def test_cameratree_attribute_is_set(self):
        tree = QNoiseTree()
        self.assertIs(self._make_demo(tree=tree).cameraTree, tree)

    def test_pipeline_is_a_filter_pipeline(self):
        self.assertIsInstance(self._make_demo().rack.pipeline, QFilterPipeline)

    def test_pipeline_reads_the_camera_source(self):
        tree = QNoiseTree()
        widget = self._make_demo(tree=tree)
        self.assertIs(widget.rack.pipeline.source, tree.source)

    def test_screen_displays_the_pipeline(self):
        widget = self._make_demo()
        self.assertIs(widget.screen.source, widget.rack.pipeline)

    def test_pipeline_runs_the_rack(self):
        widget = self._make_demo()
        self.assertIs(widget.rack.pipeline.rack, widget.rack)

    def test_layout_contains_screen(self):
        widget = self._make_demo()
        layout = widget.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.screen, items)

    def test_rack_is_a_fixed_filter_rack(self):
        widget = self._make_demo()
        self.assertIsInstance(widget.rack, QFilterRack)
        self.assertFalse(widget.rack.editable)

    def test_filters_are_added_to_the_rack(self):
        widget = self._make_demo()
        kinds = [type(f) for f in widget.rack.filters]
        self.assertEqual(kinds, [QRGBFilter, QSmoothingFilter])

    def test_filters_start_switched_off(self):
        widget = self._make_demo()
        self.assertEqual(widget.rack.activeFilters(), [])

    def test_empty_filter_list(self):
        self.assertIsInstance(self._make_demo([]), FilterDemo)

    def test_unknown_filter_name_raises(self):
        with self.assertRaises(ValueError):
            FilterDemo(QNoiseTree(), ['No Such Filter'])

    def test_deleting_the_demo_stops_the_pipeline(self):
        widget = self._make_demo()
        pipeline = widget.rack.pipeline
        widget.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        self.assertFalse(pipeline.isRunning())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
