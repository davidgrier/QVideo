'''Unit tests for demos.histogramdemo.'''
import unittest
from qtpy import QtWidgets
from QVideo.lib.QHistogramWidget import QHistogramWidget
from QVideo.lib.QVideoScreen import QVideoScreen
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo
from QVideo.demos.histogramdemo import HistogramDemo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_demo() -> HistogramDemo:
    return HistogramDemo(QNoiseTree())


class TestHistogramDemo(unittest.TestCase):

    def setUp(self):
        self.widget = make_demo()

    def test_creates_successfully(self):
        self.assertIsInstance(self.widget, HistogramDemo)

    def test_is_subclass_of_demo(self):
        self.assertIsInstance(self.widget, Demo)

    def test_screen_attribute_is_qvideoscreen(self):
        self.assertIsInstance(self.widget.screen, QVideoScreen)

    def test_histogram_attribute_is_qhistogramwidget(self):
        self.assertIsInstance(self.widget.histogram, QHistogramWidget)

    def test_histogram_connected_to_screen(self):
        self.assertIs(self.widget.histogram.screen, self.widget.screen)

    def test_controls_contains_camera_tree(self):
        items = [self.widget._controls.itemAt(i).widget()
                 for i in range(self.widget._controls.count())]
        self.assertIn(self.widget.cameraTree, items)

    def test_controls_contains_histogram(self):
        items = [self.widget._controls.itemAt(i).widget()
                 for i in range(self.widget._controls.count())]
        self.assertIn(self.widget.histogram, items)

    def test_screen_source_connected_to_tree_source(self):
        tree = QNoiseTree()
        widget = HistogramDemo(tree)
        self.assertIs(widget.screen.source, tree.source)


if __name__ == '__main__':
    unittest.main()
