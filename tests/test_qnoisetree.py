'''Unit tests for QNoiseTree.'''
import unittest
from pyqtgraph.Qt import QtWidgets
from QVideo.cameras.Noise.QNoiseTree import QNoiseTree


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestQNoiseTreeInit(unittest.TestCase):

    def test_creates_successfully(self):
        tree = QNoiseTree()
        self.assertIsInstance(tree, QNoiseTree)

    def test_color_parameter_is_disabled(self):
        tree = QNoiseTree()
        color_param = tree._parameters.get('color')
        self.assertIsNotNone(color_param)
        self.assertFalse(color_param.opts.get('enabled', True))

    def test_other_parameters_are_enabled(self):
        tree = QNoiseTree()
        width_param = tree._parameters.get('width')
        self.assertIsNotNone(width_param)
        self.assertTrue(width_param.opts.get('enabled', True))


if __name__ == '__main__':
    unittest.main()
