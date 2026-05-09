'''Unit tests for demos.filterdemo.'''
import unittest
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib import QVideoScreen
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo
from QVideo.demos.filterdemo import FilterDemo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

FILTERS = ['QRGBFilter', 'QSmoothingFilter']


class TestFilterDemo(unittest.TestCase):

    def setUp(self):
        self._p_start = patch.object(QtCore.QThread, 'start')
        self._p_move = patch.object(QtCore.QObject, 'moveToThread')
        self._p_start.start()
        self._p_move.start()

    def tearDown(self):
        self._p_start.stop()
        self._p_move.stop()

    def _make_demo(self, filters=None):
        return FilterDemo(QNoiseTree(), filters if filters is not None else FILTERS)

    def test_creates_successfully(self):
        widget = self._make_demo()
        self.assertIsInstance(widget, FilterDemo)

    def test_is_subclass_of_demo(self):
        widget = self._make_demo()
        self.assertIsInstance(widget, Demo)

    def test_screen_attribute_is_qvideoscreen(self):
        widget = self._make_demo()
        self.assertIsInstance(widget.screen, QVideoScreen)

    def test_cameratree_attribute_is_set(self):
        tree = QNoiseTree()
        widget = FilterDemo(tree, FILTERS)
        self.assertIs(widget.cameraTree, tree)

    def test_screen_source_connected_to_tree_source(self):
        tree = QNoiseTree()
        widget = FilterDemo(tree, FILTERS)
        self.assertIs(widget.screen.source, tree.source)

    def test_layout_contains_screen(self):
        widget = self._make_demo()
        layout = widget.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.screen, items)

    def test_filters_registered(self):
        widget = self._make_demo(FILTERS)
        registered = [type(f).__name__ for f in widget.screen.filter.filters]
        for name in FILTERS:
            self.assertIn(name, registered)

    def test_filter_bank_visible_after_init(self):
        widget = self._make_demo()
        self.assertFalse(widget.screen.filter.isHidden())

    def test_empty_filter_list(self):
        widget = self._make_demo([])
        self.assertIsInstance(widget, FilterDemo)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
