'''The demos are recipes: each is one documented override of _setupUi.'''
import ast
import importlib
import inspect
import unittest
from qtpy import QtWidgets
from QVideo.QCamcorder import QCamcorder
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

RECIPES = [('QVideo.demos.histogramdemo', 'HistogramDemo'),
           ('QVideo.demos.uniformitydemo', 'UniformityDemo'),
           ('QVideo.demos.circulardemo', 'CircularDemo'),
           ('QVideo.demos.trackpydemo', 'TrackpyDemo'),
           ('QVideo.demos.yolodemo', 'YoloDemo'),
           ('QVideo.demos.filterdemo', 'FilterDemo'),
           ('QVideo.demos.filterrackdemo', 'FilterRackDemo'),
           ('QVideo.demos.compositedemo', 'CompositeDemo'),
           ('QVideo.demos.combineddemo', 'CombinedDemo'),
           ('QVideo.demos.roidemo', 'ROIDemo')]


def recipe(name: str, cls: str) -> type:
    return getattr(importlib.import_module(name), cls)


class TestBases(unittest.TestCase):
    '''Both families offer the same layout of controls to a recipe.'''

    def check(self, widget):
        layout = widget._controls
        self.assertIsInstance(layout, QtWidgets.QVBoxLayout)
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertIn(widget.cameraTree if hasattr(widget, 'cameraTree')
                      else widget.cameraWidget, items)

    def test_a_demo_has_a_layout_of_controls(self):
        tree = QNoiseTree()
        self.addCleanup(tree.stop)
        self.check(Demo(tree))

    def test_a_camcorder_has_a_layout_of_controls(self):
        tree = QNoiseTree()
        self.addCleanup(tree.stop)
        self.check(QCamcorder(tree))


class TestShape(unittest.TestCase):

    def test_every_recipe_shows_where_the_frames_flow(self):
        for name, cls in RECIPES + [('QVideo.demos.demo', 'Demo')]:
            with self.subTest(recipe=cls):
                self.assertIn('Data flow::',
                              inspect.getdoc(recipe(name, cls)))

    def test_every_recipe_extends_setupui_starting_with_super(self):
        for name, cls in RECIPES:
            with self.subTest(recipe=cls):
                tree = ast.parse(inspect.getsource(recipe(name, cls)))
                methods = {node.name: node for node in tree.body[0].body
                           if isinstance(node, ast.FunctionDef)}
                self.assertIn('_setupUi', methods)
                first = ast.unparse(methods['_setupUi'].body[0])
                self.assertEqual(first, 'super()._setupUi()')


if __name__ == '__main__':
    unittest.main()
