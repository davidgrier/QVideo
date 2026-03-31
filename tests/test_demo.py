'''Unit tests for demos.demo.'''
import unittest
from qtpy import QtWidgets
from QVideo.lib import QVideoScreen
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_demo():
    return Demo(QNoiseTree())


class TestDemo(unittest.TestCase):

    def test_creates_successfully(self):
        widget = make_demo()
        self.assertIsInstance(widget, Demo)

    def test_screen_attribute_is_qvideoscreen(self):
        widget = make_demo()
        self.assertIsInstance(widget.screen, QVideoScreen)

    def test_cameratree_attribute_is_set(self):
        tree = QNoiseTree()
        widget = Demo(tree)
        self.assertIs(widget.cameraTree, tree)

    def test_screen_source_connected_to_tree_source(self):
        tree = QNoiseTree()
        widget = Demo(tree)
        self.assertIs(widget.screen.source, tree.source)

    def test_layout_contains_screen(self):
        widget = make_demo()
        layout = widget.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.screen, items)

    def test_controls_contains_tree(self):
        tree = QNoiseTree()
        widget = Demo(tree)
        items = [widget._controls.itemAt(i).widget()
                 for i in range(widget._controls.count())]
        self.assertIn(tree, items)


if __name__ == '__main__':
    unittest.main()
