'''Filters that convert color frames to gray do so through grayscale().'''
import unittest
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


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
