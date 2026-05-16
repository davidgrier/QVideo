'''Unit tests for ROIFilter and QROIFilter.'''
import unittest
import numpy as np
from qtpy import QtWidgets
from QVideo.filters.roi import ROIFilter, QROIFilter
from QVideo.lib.QVideoFilter import QVideoFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_GRAY = np.arange(100, dtype=np.uint8).reshape(10, 10)
_RGB = np.zeros((10, 10, 3), dtype=np.uint8)


def make_filter(**kwargs) -> ROIFilter:
    return ROIFilter(**kwargs)


def make_widget() -> QROIFilter:
    return QROIFilter(parent=None)


class TestROIFilterDefaults(unittest.TestCase):

    def test_default_x(self):
        f = make_filter()
        self.assertEqual(f.x, 0)

    def test_default_y(self):
        f = make_filter()
        self.assertEqual(f.y, 0)

    def test_default_w(self):
        f = make_filter()
        self.assertEqual(f.w, 128)

    def test_default_h(self):
        f = make_filter()
        self.assertEqual(f.h, 128)


class TestROIFilterProperties(unittest.TestCase):

    def test_x_setter_converts_to_int(self):
        f = make_filter()
        f.x = 3.7
        self.assertEqual(f.x, 3)

    def test_y_setter_converts_to_int(self):
        f = make_filter()
        f.y = 2.9
        self.assertEqual(f.y, 2)

    def test_w_setter_converts_to_int(self):
        f = make_filter()
        f.w = 5.1
        self.assertEqual(f.w, 5)

    def test_h_setter_converts_to_int(self):
        f = make_filter()
        f.h = 7.8
        self.assertEqual(f.h, 7)

    def test_custom_xywh(self):
        f = make_filter(x=1, y=2, w=3, h=4)
        self.assertEqual((f.x, f.y, f.w, f.h), (1, 2, 3, 4))


class TestROIFilterGet(unittest.TestCase):

    def test_get_raises_before_add(self):
        f = make_filter()
        with self.assertRaises(ValueError):
            f.get()

    def test_get_returns_ndarray(self):
        f = make_filter(x=0, y=0, w=4, h=4)
        f.add(_GRAY)
        result = f.get()
        self.assertIsInstance(result, np.ndarray)

    def test_get_crops_correct_region(self):
        f = make_filter(x=2, y=3, w=4, h=2)
        f.add(_GRAY)
        result = f.get()
        np.testing.assert_array_equal(result, _GRAY[3:5, 2:6])

    def test_get_shape_matches_wh(self):
        f = make_filter(x=0, y=0, w=5, h=3)
        f.add(_GRAY)
        result = f.get()
        self.assertEqual(result.shape, (3, 5))


class TestROIFilterClamp(unittest.TestCase):

    def test_clamp_on_first_frame(self):
        f = make_filter(x=0, y=0, w=128, h=128)
        f.add(_GRAY)  # _GRAY is 10x10
        self.assertLessEqual(f.w, 10)
        self.assertLessEqual(f.h, 10)

    def test_clamp_x_to_frame_width(self):
        f = make_filter(x=20, y=0, w=5, h=5)
        f.add(_GRAY)
        self.assertLessEqual(f.x, 9)

    def test_clamp_y_to_frame_height(self):
        f = make_filter(x=0, y=20, w=5, h=5)
        f.add(_GRAY)
        self.assertLessEqual(f.y, 9)

    def test_clamp_w_does_not_exceed_frame(self):
        f = make_filter(x=3, y=0, w=128, h=5)
        f.add(_GRAY)
        self.assertLessEqual(f.x + f.w, 10)

    def test_clamp_h_does_not_exceed_frame(self):
        f = make_filter(x=0, y=3, w=5, h=128)
        f.add(_GRAY)
        self.assertLessEqual(f.y + f.h, 10)

    def test_no_clamp_on_same_shape(self):
        f = make_filter(x=0, y=0, w=5, h=5)
        f.add(_GRAY)
        f.x = 0
        f.y = 0
        f.w = 5
        f.h = 5
        f.add(_GRAY)  # same shape: _clamp should NOT run again
        self.assertEqual(f.w, 5)
        self.assertEqual(f.h, 5)

    def test_clamp_triggered_on_shape_change(self):
        f = make_filter(x=0, y=0, w=5, h=5)
        f.add(_GRAY)           # 10x10
        _small = np.zeros((4, 4), dtype=np.uint8)
        f.add(_small)          # shape change → clamp
        self.assertLessEqual(f.w, 4)
        self.assertLessEqual(f.h, 4)


class TestROIFilterCall(unittest.TestCase):

    def test_call_returns_cropped_frame(self):
        f = make_filter(x=0, y=0, w=4, h=4)
        result = f(_GRAY)
        self.assertEqual(result.shape, (4, 4))

    def test_call_works_on_rgb(self):
        f = make_filter(x=0, y=0, w=4, h=4)
        result = f(_RGB)
        self.assertEqual(result.shape, (4, 4, 3))


class TestQROIFilter(unittest.TestCase):

    def test_is_qvideofilter(self):
        widget = make_widget()
        self.assertIsInstance(widget, QVideoFilter)

    def test_filter_is_roi_filter(self):
        widget = make_widget()
        self.assertIsInstance(widget.filter, ROIFilter)

    def test_title(self):
        widget = make_widget()
        self.assertEqual(widget.title(), 'Region of Interest')

    def test_initially_unchecked(self):
        widget = make_widget()
        self.assertFalse(widget.isChecked())

    def test_has_x_spinbox(self):
        widget = make_widget()
        self.assertIsNotNone(widget._xSpinbox)

    def test_has_y_spinbox(self):
        widget = make_widget()
        self.assertIsNotNone(widget._ySpinbox)

    def test_has_w_spinbox(self):
        widget = make_widget()
        self.assertIsNotNone(widget._wSpinbox)

    def test_has_h_spinbox(self):
        widget = make_widget()
        self.assertIsNotNone(widget._hSpinbox)

    def test_setX_updates_filter(self):
        widget = make_widget()
        widget.setX(3)
        self.assertEqual(widget.filter.x, 3)

    def test_setY_updates_filter(self):
        widget = make_widget()
        widget.setY(4)
        self.assertEqual(widget.filter.y, 4)

    def test_setW_updates_filter(self):
        widget = make_widget()
        widget.setW(64)
        self.assertEqual(widget.filter.w, 64)

    def test_setH_updates_filter(self):
        widget = make_widget()
        widget.setH(64)
        self.assertEqual(widget.filter.h, 64)

    def test_setX_syncs_spinbox(self):
        widget = make_widget()
        widget.setX(5)
        self.assertEqual(widget._xSpinbox.value(), 5)

    def test_setY_syncs_spinbox(self):
        widget = make_widget()
        widget.setY(6)
        self.assertEqual(widget._ySpinbox.value(), 6)

    def test_setW_syncs_spinbox(self):
        widget = make_widget()
        widget.setW(32)
        self.assertEqual(widget._wSpinbox.value(), 32)

    def test_setH_syncs_spinbox(self):
        widget = make_widget()
        widget.setH(32)
        self.assertEqual(widget._hSpinbox.value(), 32)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_GRAY)
        np.testing.assert_array_equal(result, _GRAY)

    def test_call_when_checked_returns_crop(self):
        widget = make_widget()
        widget.setChecked(True)
        widget.setW(4)
        widget.setH(4)
        result = widget(_GRAY)
        self.assertEqual(result.shape, (4, 4))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
