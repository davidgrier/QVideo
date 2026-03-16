'''Unit tests for demos.ROIdemo.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtWidgets, QtTest
from QVideo.cameras.Noise.QNoiseTree import QNoiseTree
from QVideo.demos.ROIdemo import ROIFilter, ROIdemo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_roi(fps=30., pos=None, size=None):
    return ROIFilter(fps, pos or [0, 0], size or [3, 2])


def make_widget():
    return ROIdemo(QNoiseTree())


class TestROIFilterInit(unittest.TestCase):

    def test_fps_stored(self):
        roi = make_roi(fps=25.)
        self.assertAlmostEqual(roi.fps, 25.)

    def test_has_new_frame_signal(self):
        roi = make_roi()
        self.assertTrue(hasattr(roi, 'newFrame'))


class TestROIFilterCrop(unittest.TestCase):

    def setUp(self):
        self.frame = np.arange(100, dtype=np.uint8).reshape(10, 10)
        self.roi = make_roi(pos=[0, 0], size=[3, 2])

    def test_crop_emits_new_frame(self):
        spy = QtTest.QSignalSpy(self.roi.newFrame)
        self.roi.crop(self.frame)
        self.assertEqual(len(spy), 1)

    def test_crop_shape(self):
        spy = QtTest.QSignalSpy(self.roi.newFrame)
        self.roi.crop(self.frame)
        self.assertEqual(spy[0][0].shape, (2, 3))

    def test_crop_correct_region(self):
        spy = QtTest.QSignalSpy(self.roi.newFrame)
        self.roi.crop(self.frame)
        np.testing.assert_array_equal(spy[0][0], self.frame[0:2, 0:3])


class TestROIdemoConstants(unittest.TestCase):

    def test_roi_pos_default(self):
        self.assertEqual(ROIdemo.ROI_POS, [100, 100])

    def test_roi_size_default(self):
        self.assertEqual(ROIdemo.ROI_SIZE, [400, 400])


class TestROIdemo(unittest.TestCase):

    def setUp(self):
        self.widget = make_widget()

    def test_creates_successfully(self):
        self.assertIsInstance(self.widget, ROIdemo)

    def test_roi_is_roi_filter(self):
        self.assertIsInstance(self.widget.roi, ROIFilter)

    def test_roi_pos_matches_class_constant(self):
        pos = self.widget.roi.pos()
        self.assertAlmostEqual(pos[0], ROIdemo.ROI_POS[0])
        self.assertAlmostEqual(pos[1], ROIdemo.ROI_POS[1])

    def test_roi_size_matches_class_constant(self):
        size = self.widget.roi.size()
        self.assertAlmostEqual(size[0], ROIdemo.ROI_SIZE[0])
        self.assertAlmostEqual(size[1], ROIdemo.ROI_SIZE[1])

    def test_dvr_filename_set(self):
        self.assertIn('roidemo.avi', self.widget.dvr.filename)

    def test_recording_locks_roi(self):
        self.widget.recording(True)
        self.assertFalse(self.widget.roi.movable)

    def test_not_recording_unlocks_roi(self):
        self.widget.recording(True)
        self.widget.recording(False)
        self.assertTrue(self.widget.roi.movable)


if __name__ == '__main__':
    unittest.main()
