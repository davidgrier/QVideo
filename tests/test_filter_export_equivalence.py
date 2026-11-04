'''The code that a filter exports does what the filter does.'''
import importlib
import inspect
import pkgutil
import unittest

import cv2
import numpy as np
from qtpy import QtWidgets

import QVideo.filters
from QVideo.filters.artistic import CartoonFilter, PencilSketchFilter
from QVideo.filters.dog import DoGFilter
from QVideo.filters.edge import EdgeFilter
from QVideo.filters.exposure import ExposureFilter
from QVideo.filters.gamma import GammaFilter
from QVideo.filters.invert import InvertFilter
from QVideo.filters.laplacian import LaplacianFilter
from QVideo.filters.rgb import RGBFilter
from QVideo.filters.roi import ROIFilter
from QVideo.filters.smoothing import SmoothingFilter
from QVideo.filters.sobel import SobelFilter
from QVideo.filters.threshold import ThresholdFilter
from QVideo.filters.unsharp import UnsharpFilter
from QVideo.lib.QVideoFilter import GRAY_LINES, VideoFilter, renderPipeline

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

rng = np.random.default_rng(1)
GRAY = rng.integers(0, 256, (48, 64), dtype=np.uint8)
COLOR = rng.integers(0, 256, (48, 64, 3), dtype=np.uint8)

#: Every filter that exports, with settings that are not the defaults, so
#: that the exported code has to carry them.
CASES = [
    EdgeFilter(low=30, high=90),
    ROIFilter(x=3, y=4, w=20, h=10),
    LaplacianFilter(ksize=3, sigma=0),
    LaplacianFilter(ksize=5, sigma=1.5),
    RGBFilter(channel=0),
    RGBFilter(channel=1),
    RGBFilter(channel=2),
    GammaFilter(gamma=2.2),
    InvertFilter(),
    UnsharpFilter(radius=2., amount=1.5),
    DoGFilter(),
    SobelFilter(direction='Horizontal', ksize=5),
    SobelFilter(direction='Vertical', ksize=3),
    SobelFilter(direction='Magnitude', ksize=5),
    ThresholdFilter(method='Global', threshold=100),
    ThresholdFilter(method='Otsu'),
    ThresholdFilter(method='Adaptive Mean', block_size=15),
    ThresholdFilter(method='Adaptive Gaussian', block_size=15),
    SmoothingFilter(method='box', width=5),
    SmoothingFilter(method='median', width=7),
    SmoothingFilter(method='gaussian', width=9),
    ExposureFilter(method='Log'),
    ExposureFilter(method='Sigmoid', cutoff=100., gain=5.),
    ExposureFilter(method='CLAHE', clip_limit=3., tile_size=4),
    PencilSketchFilter(gray=False),
    PencilSketchFilter(gray=True),
    CartoonFilter(),
]


def describe(f: VideoFilter) -> str:
    settings = {k: v for k, v in vars(f).items()
                if k.startswith('_') and isinstance(v, (int, float, str))}
    return f'{type(f).__name__}{settings}'


class TestExportedCode(unittest.TestCase):

    def check(self, f, image, source):
        """Compare the code of *f* with *f*, on *image*."""
        namespace = {}
        exec(source, namespace)
        want = f(image.copy())
        got = namespace['filter'](image.copy())
        self.assertEqual(got.shape, want.shape)
        np.testing.assert_array_equal(got, want)

    def test_the_exported_function_gives_the_result_of_the_filter(self):
        for f in CASES:
            source = renderPipeline([f.to_code()], [])
            for name, image in (('gray', GRAY), ('color', COLOR)):
                with self.subTest(filter=describe(f), image=name):
                    self.check(f, image, source)

    def test_a_fragment_imports_what_it_uses_and_only_that(self):
        for f in CASES:
            code = f.to_code()
            with self.subTest(filter=describe(f)):
                namespace = {}
                for line in code.imports:
                    exec(line, namespace)
                namespace['image'] = COLOR.copy()
                exec('\n'.join(code.lines), namespace)
                source = '\n'.join(code.lines)
                for line in code.imports:
                    alias = line.split()[-1]
                    self.assertIn(f'{alias}.', source, line)

    def test_a_fragment_says_what_it_does(self):
        for f in CASES:
            with self.subTest(filter=describe(f)):
                self.assertTrue(f.to_code().comment)

    def test_the_gray_lines_make_an_image_gray(self):
        namespace = {'cv2': cv2, 'image': COLOR.copy()}
        exec('\n'.join(GRAY_LINES), namespace)
        self.assertEqual(namespace['image'].ndim, 2)
        namespace = {'cv2': cv2, 'image': GRAY.copy()}
        exec('\n'.join(GRAY_LINES), namespace)
        np.testing.assert_array_equal(namespace['image'], GRAY)


class TestEveryExportingFilterIsChecked(unittest.TestCase):

    def test_no_filter_that_exports_is_missing_from_the_cases(self):
        checked = {type(f) for f in CASES}
        for module in pkgutil.iter_modules(QVideo.filters.__path__):
            try:
                found = importlib.import_module(
                    f'QVideo.filters.{module.name}')
            except ImportError:     # a soft dependency is missing
                continue
            for name, cls in inspect.getmembers(found, inspect.isclass):
                if (issubclass(cls, VideoFilter)
                        and cls.__module__ == found.__name__
                        and cls.to_code is not VideoFilter.to_code):
                    with self.subTest(filter=name):
                        self.assertIn(cls, checked)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
