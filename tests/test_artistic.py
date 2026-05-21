'''Unit tests for PencilSketchFilter, CartoonFilter, and their Qt widgets.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib.AsyncVideoFilter import AsyncVideoFilter
from QVideo.filters.artistic import (
    PencilSketchFilter, QPencilSketchFilter,
    CartoonFilter, QCartoonFilter,
)


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_SHAPE_COLOR = (32, 32, 3)
_SHAPE_GRAY = (32, 32)
_COLOR = np.random.randint(0, 256, _SHAPE_COLOR, dtype=np.uint8)
_GRAY = np.random.randint(0, 256, _SHAPE_GRAY, dtype=np.uint8)


def make_pencil(**kwargs) -> PencilSketchFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return PencilSketchFilter(**kwargs)


def make_cartoon(**kwargs) -> CartoonFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return CartoonFilter(**kwargs)


def make_pencil_widget() -> QPencilSketchFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return QPencilSketchFilter(parent=None)


def make_cartoon_widget() -> QCartoonFilter:
    with patch.object(QtCore.QThread, 'start'), \
         patch.object(QtCore.QObject, 'moveToThread'):
        return QCartoonFilter(parent=None)


class TestPencilSketchFilter(unittest.TestCase):

    def setUp(self):
        self._p_start = patch.object(QtCore.QThread, 'start')
        self._p_move = patch.object(QtCore.QObject, 'moveToThread')
        self._p_start.start()
        self._p_move.start()

    def tearDown(self):
        self._p_start.stop()
        self._p_move.stop()

    def test_is_async_video_filter(self):
        self.assertIsInstance(PencilSketchFilter(), AsyncVideoFilter)

    def test_default_params(self):
        f = PencilSketchFilter()
        self.assertAlmostEqual(f.sigma_s, 60.)
        self.assertAlmostEqual(f.sigma_r, 0.07)
        self.assertAlmostEqual(f.shade_factor, 0.05)
        self.assertFalse(f.gray)

    def test_color_output_shape(self):
        result = make_pencil().process(_COLOR)
        self.assertEqual(result.shape, _SHAPE_COLOR)

    def test_gray_output_is_2d(self):
        result = make_pencil(gray=True).process(_COLOR)
        self.assertEqual(result.ndim, 2)

    def test_grayscale_input_accepted(self):
        result = make_pencil().process(_GRAY)
        self.assertIsNotNone(result)

    def test_result_is_uint8(self):
        result = make_pencil().process(_COLOR)
        self.assertEqual(result.dtype, np.uint8)

    def test_does_not_mutate_input(self):
        original = _COLOR.copy()
        make_pencil().process(_COLOR)
        np.testing.assert_array_equal(_COLOR, original)

    def test_to_code_returns_filter_code(self):
        from QVideo.lib.QVideoFilter import FilterCode
        code = make_pencil().to_code()
        self.assertIsInstance(code, FilterCode)

    def test_to_code_imports_cv2(self):
        self.assertIn('import cv2', make_pencil().to_code().imports)

    def test_to_code_gray_uses_first_return(self):
        code = make_pencil(gray=True).to_code()
        self.assertTrue(any('image, _' in line for line in code.lines))

    def test_to_code_color_uses_second_return(self):
        code = make_pencil(gray=False).to_code()
        self.assertTrue(any('_, image' in line for line in code.lines))


class TestCartoonFilter(unittest.TestCase):

    def setUp(self):
        self._p_start = patch.object(QtCore.QThread, 'start')
        self._p_move = patch.object(QtCore.QObject, 'moveToThread')
        self._p_start.start()
        self._p_move.start()

    def tearDown(self):
        self._p_start.stop()
        self._p_move.stop()

    def test_is_async_video_filter(self):
        self.assertIsInstance(CartoonFilter(), AsyncVideoFilter)

    def test_default_params(self):
        f = CartoonFilter()
        self.assertAlmostEqual(f.sigma_s, 150.)
        self.assertAlmostEqual(f.sigma_r, 0.45)

    def test_color_output_shape(self):
        result = make_cartoon().process(_COLOR)
        self.assertEqual(result.shape, _SHAPE_COLOR)

    def test_grayscale_input_accepted(self):
        result = make_cartoon().process(_GRAY)
        self.assertIsNotNone(result)

    def test_result_is_uint8(self):
        result = make_cartoon().process(_COLOR)
        self.assertEqual(result.dtype, np.uint8)

    def test_does_not_mutate_input(self):
        original = _COLOR.copy()
        make_cartoon().process(_COLOR)
        np.testing.assert_array_equal(_COLOR, original)

    def test_to_code_returns_filter_code(self):
        from QVideo.lib.QVideoFilter import FilterCode
        code = make_cartoon().to_code()
        self.assertIsInstance(code, FilterCode)

    def test_to_code_imports_cv2(self):
        self.assertIn('import cv2', make_cartoon().to_code().imports)

    def test_to_code_has_stylization_call(self):
        code = make_cartoon().to_code()
        self.assertTrue(any('stylization' in line for line in code.lines))


class TestQPencilSketchFilter(unittest.TestCase):

    def setUp(self):
        self._p_start = patch.object(QtCore.QThread, 'start')
        self._p_move = patch.object(QtCore.QObject, 'moveToThread')
        self._p_start.start()
        self._p_move.start()

    def tearDown(self):
        self._p_start.stop()
        self._p_move.stop()

    def test_filter_is_pencilsketch(self):
        self.assertIsInstance(QPencilSketchFilter().filter, PencilSketchFilter)

    def test_title(self):
        self.assertEqual(QPencilSketchFilter().title(), 'Pencil Sketch')

    def test_display_name(self):
        self.assertEqual(QPencilSketchFilter.display_name, 'Pencil Sketch')

    def test_display_category(self):
        self.assertEqual(QPencilSketchFilter.display_category, 'Artistic')

    def test_has_sigma_s_spinbox(self):
        self.assertTrue(hasattr(QPencilSketchFilter(), '_sigmaS'))

    def test_has_sigma_r_spinbox(self):
        self.assertTrue(hasattr(QPencilSketchFilter(), '_sigmaR'))

    def test_has_shade_spinbox(self):
        self.assertTrue(hasattr(QPencilSketchFilter(), '_shade'))

    def test_has_gray_checkbox(self):
        w = QPencilSketchFilter()
        self.assertIsInstance(w._grayBox, QtWidgets.QCheckBox)

    def test_set_sigma_s_updates_filter(self):
        w = QPencilSketchFilter()
        w._setSigmaS(100.)
        self.assertAlmostEqual(w.filter.sigma_s, 100.)

    def test_set_sigma_r_updates_filter(self):
        w = QPencilSketchFilter()
        w._setSigmaR(0.5)
        self.assertAlmostEqual(w.filter.sigma_r, 0.5)

    def test_set_shade_updates_filter(self):
        w = QPencilSketchFilter()
        w._setShade(0.05)
        self.assertAlmostEqual(w.filter.shade_factor, 0.05)

    def test_set_gray_updates_filter(self):
        w = QPencilSketchFilter()
        w._setGray(True)
        self.assertTrue(w.filter.gray)

    def test_call_unchecked_returns_frame(self):
        w = QPencilSketchFilter()
        np.testing.assert_array_equal(w(_COLOR), _COLOR)


class TestQCartoonFilter(unittest.TestCase):

    def setUp(self):
        self._p_start = patch.object(QtCore.QThread, 'start')
        self._p_move = patch.object(QtCore.QObject, 'moveToThread')
        self._p_start.start()
        self._p_move.start()

    def tearDown(self):
        self._p_start.stop()
        self._p_move.stop()

    def test_filter_is_cartoon(self):
        self.assertIsInstance(QCartoonFilter().filter, CartoonFilter)

    def test_title(self):
        self.assertEqual(QCartoonFilter().title(), 'Cartoon')

    def test_display_name(self):
        self.assertEqual(QCartoonFilter.display_name, 'Cartoon')

    def test_display_category(self):
        self.assertEqual(QCartoonFilter.display_category, 'Artistic')

    def test_has_sigma_s_spinbox(self):
        self.assertTrue(hasattr(QCartoonFilter(), '_sigmaS'))

    def test_has_sigma_r_spinbox(self):
        self.assertTrue(hasattr(QCartoonFilter(), '_sigmaR'))

    def test_set_sigma_s_updates_filter(self):
        w = QCartoonFilter()
        w._setSigmaS(50.)
        self.assertAlmostEqual(w.filter.sigma_s, 50.)

    def test_set_sigma_r_updates_filter(self):
        w = QCartoonFilter()
        w._setSigmaR(0.3)
        self.assertAlmostEqual(w.filter.sigma_r, 0.3)

    def test_call_unchecked_returns_frame(self):
        w = QCartoonFilter()
        np.testing.assert_array_equal(w(_COLOR), _COLOR)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
