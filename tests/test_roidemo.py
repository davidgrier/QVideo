'''Unit tests for demos.ROIDemo.'''
import unittest
import numpy as np
from qtpy import QtWidgets
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.lib.videotypes import FrameInfo
from QVideo.demos.ROIdemo import CropROI, ROIDemo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_roi(fps=30., pos=None, size=None):
    return CropROI(fps, pos or [0, 0], size or [3, 2])


def make_widget():
    return ROIDemo(QNoiseTree())


class TestCropROIInit(unittest.TestCase):

    def test_fps_stored(self):
        roi = make_roi(fps=25.)
        self.assertAlmostEqual(roi.fps, 25.)

    def test_has_new_frame_signal(self):
        roi = make_roi()
        self.assertTrue(hasattr(roi, 'newFrame'))


class TestCropROICrop(unittest.TestCase):

    def setUp(self):
        self.frame = np.arange(100, dtype=np.uint8).reshape(10, 10)
        self.roi = make_roi(pos=[0, 0], size=[3, 2])
        self.received = []
        self.roi.newFrame.connect(
            lambda frame, info: self.received.append((frame, info)))

    def test_crop_emits_new_frame(self):
        self.roi.crop(self.frame)
        self.assertEqual(len(self.received), 1)

    def test_crop_shape(self):
        self.roi.crop(self.frame)
        self.assertEqual(self.received[0][0].shape, (2, 3))

    def test_crop_correct_region(self):
        self.roi.crop(self.frame)
        np.testing.assert_array_equal(self.received[0][0],
                                      self.frame[0:2, 0:3])

    def test_crop_does_not_share_memory_with_the_frame(self):
        self.roi.crop(self.frame)
        self.assertFalse(np.shares_memory(self.received[0][0], self.frame))

    def test_crop_passes_frame_info_through(self):
        info = FrameInfo(7, 1.5)
        self.roi.crop(self.frame, info)
        self.assertIs(self.received[0][1], info)

    def test_crop_without_info_emits_none(self):
        self.roi.crop(self.frame)
        self.assertIsNone(self.received[0][1])


class TestROIDemoConstants(unittest.TestCase):

    def test_display_rate_default(self):
        self.assertEqual(ROIDemo.DISPLAY_RATE, 30)


class TestROIDemo(unittest.TestCase):

    def setUp(self):
        self.widget = make_widget()

    def test_creates_successfully(self):
        self.assertIsInstance(self.widget, ROIDemo)

    def test_roi_is_crop_roi(self):
        self.assertIsInstance(self.widget.roi, CropROI)

    def test_roi_pos_matches_geometry(self):
        expected_pos, _ = self.widget._roiGeometry()
        pos = self.widget.roi.pos()
        self.assertAlmostEqual(pos[0], expected_pos[0])
        self.assertAlmostEqual(pos[1], expected_pos[1])

    def test_roi_size_matches_geometry(self):
        _, expected_size = self.widget._roiGeometry()
        size = self.widget.roi.size()
        self.assertAlmostEqual(size[0], expected_size[0])
        self.assertAlmostEqual(size[1], expected_size[1])

    def test_roi_size_divisible_by_8(self):
        _, size = self.widget._roiGeometry()
        self.assertEqual(size[0] % 8, 0)
        self.assertEqual(size[1] % 8, 0)

    def test_roi_centered(self):
        shape = self.widget.source.shape
        pos, size = self.widget._roiGeometry()
        self.assertEqual(pos[0], (shape.width() - size[0]) // 2)
        self.assertEqual(pos[1], (shape.height() - size[1]) // 2)

    def test_dvr_source_is_roi(self):
        self.assertIs(self.widget.dvr.source, self.widget.roi)

    def test_dvr_filename_set(self):
        self.assertIn('roidemo.avi', self.widget.dvr.filename)

    def test_recording_locks_roi(self):
        self.widget.recording(True)
        self.assertFalse(self.widget.roi.movable)

    def test_recording_passes_capture_info_to_the_recorder(self):
        received = []
        self.widget.roi.newFrame.connect(
            lambda frame, info: received.append(info))
        info = FrameInfo(3, 2.5)
        self.widget.recording(True)
        self.widget.source.newFrame.emit(
            np.zeros((480, 640), dtype=np.uint8), info)
        self.widget.recording(False)
        self.assertEqual(received, [info])

    def test_not_recording_unlocks_roi(self):
        self.widget.recording(True)
        self.widget.recording(False)
        self.assertTrue(self.widget.roi.movable)


if __name__ == '__main__':
    unittest.main()
