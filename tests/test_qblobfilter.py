'''Unit tests for BlobFilter and QBlobFilter.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtWidgets
from QVideo.filters.QBlobFilter import BlobFilter, QBlobFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640), dtype=np.uint8)

# Binary frame with a single foreground blob
_BINARY_FRAME = np.zeros((10, 10), dtype=np.uint8)
_BINARY_FRAME[3:7, 3:7] = 255


def make_filter() -> BlobFilter:
    return BlobFilter()


def make_widget() -> QBlobFilter:
    return QBlobFilter(parent=None)


class TestBlobFilter(unittest.TestCase):

    def test_get_returns_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.get())

    def test_get_returns_ndarray(self):
        f = make_filter()
        f.add(_BINARY_FRAME)
        result = f.get()
        self.assertIsInstance(result, np.ndarray)

    def test_get_returns_bgr_image(self):
        f = make_filter()
        f.add(_BINARY_FRAME)
        result = f.get()
        self.assertEqual(result.ndim, 3)
        self.assertEqual(result.shape[2], 3)

    def test_get_preserves_spatial_dimensions(self):
        f = make_filter()
        f.add(_BINARY_FRAME)
        result = f.get()
        self.assertEqual(result.shape[:2], _BINARY_FRAME.shape)

    def test_background_pixels_are_black(self):
        f = make_filter()
        f.add(_BINARY_FRAME)
        result = f.get()
        np.testing.assert_array_equal(result[0, 0], [0, 0, 0])

    def test_get_calls_connected_components(self):
        f = make_filter()
        f.add(_BINARY_FRAME)
        labels = np.zeros((10, 10), dtype=np.int32)
        labels[3:7, 3:7] = 1
        color3 = np.zeros((10, 10, 3), dtype=np.uint8)
        with patch('cv2.connectedComponents', return_value=(2, labels)) as mock_cc, \
             patch('cv2.merge', return_value=color3), \
             patch('cv2.cvtColor', return_value=color3):
            f.get()
        mock_cc.assert_called_once_with(_BINARY_FRAME)

    def test_call_applies_blob_coloring(self):
        f = make_filter()
        result = f(_BINARY_FRAME)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape[2], 3)


class TestQBlobFilter(unittest.TestCase):

    def test_is_qvideofilter(self):
        from QVideo.lib.QVideoFilter import QVideoFilter
        widget = make_widget()
        self.assertIsInstance(widget, QVideoFilter)

    def test_filter_is_blob_filter(self):
        widget = make_widget()
        self.assertIsInstance(widget.filter, BlobFilter)

    def test_title(self):
        widget = make_widget()
        self.assertEqual(widget.title(), 'Blob')

    def test_initially_unchecked(self):
        widget = make_widget()
        self.assertFalse(widget.isChecked())

    def test_call_when_unchecked_returns_frame_unchanged(self):
        widget = make_widget()
        result = widget(_BINARY_FRAME)
        np.testing.assert_array_equal(result, _BINARY_FRAME)

    def test_call_when_checked_applies_blob_coloring(self):
        widget = make_widget()
        widget.setChecked(True)
        result = widget(_BINARY_FRAME)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape[2], 3)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
