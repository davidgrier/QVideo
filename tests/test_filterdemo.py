'''Unit tests for demos.filterdemo.'''
import unittest
from qtpy import QtWidgets
from QVideo.lib import QFilterRack, QFilterStack, QVideoScreen
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
        self.addCleanup(widget.stack.stop)
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

    def test_stack_is_a_filter_stack(self):
        self.assertIsInstance(self._make_demo().stack, QFilterStack)

    def test_stack_reads_the_camera_source(self):
        tree = QNoiseTree()
        widget = self._make_demo(tree=tree)
        self.assertIs(widget.stack.source, tree.source)

    def test_screen_displays_the_stack(self):
        widget = self._make_demo()
        self.assertIs(widget.screen.source, widget.stack)

    def test_stack_runs_the_rack(self):
        widget = self._make_demo()
        self.assertIs(widget.stack.rack, widget.rack)

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

    def test_closing_stops_the_stack(self):
        widget = self._make_demo()
        widget.close()
        self.assertFalse(widget.stack.isRunning())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
