'''Unit tests for demos.filterdemo.'''
import unittest
from pyqtgraph.Qt import QtWidgets
from QVideo.lib import QVideoScreen
from QVideo.cameras.Noise.QNoiseTree import QNoiseTree
from QVideo.demos.filterdemo import demo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

FILTERS = ['QRGBFilter', 'QBlurFilter']


def make_demo(filters=None):
    return demo(QNoiseTree(), filters or FILTERS)


class TestFilterDemo(unittest.TestCase):

    def test_creates_successfully(self):
        widget = make_demo()
        self.assertIsInstance(widget, demo)

    def test_screen_attribute_is_qvideoscreen(self):
        widget = make_demo()
        self.assertIsInstance(widget.screen, QVideoScreen)

    def test_cameratree_attribute_is_set(self):
        tree = QNoiseTree()
        widget = demo(tree, FILTERS)
        self.assertIs(widget.cameraTree, tree)

    def test_screen_source_connected_to_tree_source(self):
        tree = QNoiseTree()
        widget = demo(tree, FILTERS)
        self.assertIs(widget.screen.source, tree.source)

    def test_layout_contains_screen(self):
        widget = make_demo()
        layout = widget.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.screen, items)

    def test_filters_registered(self):
        widget = make_demo(FILTERS)
        registered = [type(f).__name__ for f in widget.screen.filter.filters]
        for name in FILTERS:
            self.assertIn(name, registered)

    def test_filter_bank_visible_after_init(self):
        widget = make_demo()
        self.assertFalse(widget.screen.filter.isHidden())

    def test_empty_filter_list(self):
        widget = make_demo([])
        self.assertIsInstance(widget, demo)


if __name__ == '__main__':
    unittest.main()
