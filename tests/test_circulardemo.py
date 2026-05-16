'''Unit tests for demos.circulardemo.'''
import unittest
from qtpy import QtWidgets

from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo
from QVideo.demos.circulardemo import CircularDemo
from QVideo.dvr.QCircularDVRWidget import QCircularDVRWidget
from QVideo.lib.QVideoScreen import QVideoScreen


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_demo() -> CircularDemo:
    return CircularDemo(QNoiseTree())


class TestCircularDemo(unittest.TestCase):

    def setUp(self):
        self.widget = make_demo()

    def test_creates_successfully(self):
        self.assertIsInstance(self.widget, CircularDemo)

    def test_is_subclass_of_demo(self):
        self.assertIsInstance(self.widget, Demo)

    def test_screen_attribute_is_qvideoscreen(self):
        self.assertIsInstance(self.widget.screen, QVideoScreen)

    def test_dvr_attribute_is_qcirculardvrwidget(self):
        self.assertIsInstance(self.widget.dvr, QCircularDVRWidget)

    def test_dvr_source_is_screen_source(self):
        self.assertIs(self.widget.dvr.source, self.widget.screen.source)

    def test_controls_contains_camera_tree(self):
        items = [self.widget._controls.itemAt(i).widget()
                 for i in range(self.widget._controls.count())]
        self.assertIn(self.widget.cameraTree, items)

    def test_controls_contains_dvr(self):
        items = [self.widget._controls.itemAt(i).widget()
                 for i in range(self.widget._controls.count())]
        self.assertIn(self.widget.dvr, items)

    def test_different_camera_trees_give_independent_demos(self):
        tree1 = QNoiseTree()
        tree2 = QNoiseTree()
        d1 = CircularDemo(tree1)
        d2 = CircularDemo(tree2)
        self.assertIsNot(d1.dvr, d2.dvr)


if __name__ == '__main__':
    unittest.main()
