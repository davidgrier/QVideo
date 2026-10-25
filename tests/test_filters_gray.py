'''Filters that convert color frames to gray do so through grayscale().'''
import unittest
import cv2
import numpy as np
from qtpy import QtWidgets
from QVideo.filters import (CircleTransformFilter, DoGFilter,
                            LaplacianFilter, SobelFilter, ThresholdFilter)
from QVideo.lib.imageops import grayscale


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_COLOR = np.random.default_rng(3).integers(0, 256, (40, 48, 3),
                                           dtype=np.uint8)


class TestColorIsProcessedAsLuminance(unittest.TestCase):

    def check(self, cls):
        np.testing.assert_array_equal(cls()(_COLOR), cls()(grayscale(_COLOR)))

    def test_sobel(self):
        self.check(SobelFilter)

    def test_laplacian(self):
        self.check(LaplacianFilter)

    def test_threshold(self):
        self.check(ThresholdFilter)

    def test_dog(self):
        self.check(DoGFilter)

    def test_circle_transform(self):
        self.check(CircleTransformFilter)


class TestExportedCode(unittest.TestCase):
    '''to_code() describes the same conversion the filter performs.'''

    def run_code(self, f):
        code = f.to_code()
        namespace = {'cv2': cv2, 'np': np, 'image': _COLOR.copy()}
        exec('\n'.join(code.lines), namespace)
        return code, namespace['image']

    def check(self, cls):
        f = cls()
        code, exported = self.run_code(f)
        source = '\n'.join(code.lines)
        self.assertIn('COLOR_RGB2GRAY', source)
        self.assertNotIn('mean(axis=2)', source)
        self.assertIn('import cv2', code.imports)
        np.testing.assert_array_equal(exported, f(_COLOR))

    def test_sobel(self):
        self.check(SobelFilter)

    def test_laplacian(self):
        self.check(LaplacianFilter)

    def test_threshold(self):
        self.check(ThresholdFilter)

    def test_dog(self):
        self.check(DoGFilter)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
