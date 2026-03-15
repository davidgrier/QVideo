'''Unit tests for QOpenCVCamera.'''
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from pyqtgraph.Qt import QtWidgets, QtCore, QtTest
from QVideo.cameras.OpenCV.QOpenCVCamera import QOpenCVCamera, QOpenCVSource


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME_BGR = np.zeros((480, 640, 3), dtype=np.uint8)
_FRAME_GRAY = np.zeros((480, 640), dtype=np.uint8)


def make_mock_device(width=640, height=480, fps=30.,
                     read_ok=True, frame=None):
    '''Return a MagicMock standing in for cv2.VideoCapture.'''
    if frame is None:
        frame = _FRAME_BGR.copy()
    device = MagicMock()
    device.read.return_value = (read_ok, frame)

    def _get(prop):
        return {QOpenCVCamera.WIDTH: width,
                QOpenCVCamera.HEIGHT: height,
                QOpenCVCamera.FPS: fps}.get(prop, 0)

    device.get.side_effect = _get
    return device


def make_camera(cameraID=0, mirrored=False, flipped=False, gray=False,
                width=640, height=480, fps=30.,
                read_ok=True, frame=None):
    '''Return a QOpenCVCamera with a mocked VideoCapture device.'''
    device = make_mock_device(width=width, height=height, fps=fps,
                              read_ok=read_ok, frame=frame)
    with patch('cv2.VideoCapture', return_value=device):
        cam = QOpenCVCamera(cameraID=cameraID, mirrored=mirrored,
                            flipped=flipped, gray=gray)
    return cam


class TestInit(unittest.TestCase):

    def test_camera_id_stored(self):
        cam = make_camera()
        self.assertEqual(cam.cameraID, 0)

    def test_custom_camera_id(self):
        cam = make_camera(cameraID=2)
        self.assertEqual(cam.cameraID, 2)

    def test_opens_on_init(self):
        cam = make_camera()
        self.assertTrue(cam.isOpen())

    def test_default_mirrored_false(self):
        cam = make_camera()
        self.assertFalse(cam.mirrored)

    def test_default_flipped_false(self):
        cam = make_camera()
        self.assertFalse(cam.flipped)

    def test_default_gray_false(self):
        cam = make_camera()
        self.assertFalse(cam.gray)

    def test_mirrored_kwarg(self):
        cam = make_camera(mirrored=True)
        self.assertTrue(cam.mirrored)

    def test_flipped_kwarg(self):
        cam = make_camera(flipped=True)
        self.assertTrue(cam.flipped)

    def test_gray_kwarg(self):
        cam = make_camera(gray=True)
        self.assertTrue(cam.gray)

    def test_name_is_class_name(self):
        cam = make_camera()
        self.assertEqual(cam.name, 'QOpenCVCamera')


class TestInitialize(unittest.TestCase):

    def test_uses_v4l2_on_linux(self):
        import cv2
        device = make_mock_device()
        with patch('platform.system', return_value='Linux'):
            with patch('cv2.VideoCapture', return_value=device) as mock_cap:
                QOpenCVCamera()
        mock_cap.assert_called_with(0, cv2.CAP_V4L2)

    def test_uses_cap_any_on_macos(self):
        import cv2
        device = make_mock_device()
        with patch('platform.system', return_value='Darwin'):
            with patch('cv2.VideoCapture', return_value=device) as mock_cap:
                QOpenCVCamera()
        mock_cap.assert_called_with(0, cv2.CAP_ANY)

    def test_initialize_fails_if_no_frame(self):
        with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
            cam = make_camera(read_ok=False)
        self.assertFalse(cam.isOpen())

    def test_device_properties_registered_on_open(self):
        cam = make_camera()
        for name in ('width', 'height', 'fps', 'color'):
            self.assertIn(name, cam.properties)

    def test_transform_properties_registered_before_open(self):
        # mirrored/flipped/gray are registered in __init__, not _initialize
        device = make_mock_device(read_ok=False)
        with patch('cv2.VideoCapture', return_value=device):
            with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
                cam = QOpenCVCamera()
        for name in ('mirrored', 'flipped', 'gray'):
            self.assertIn(name, cam.properties)


class TestDeinitialize(unittest.TestCase):

    def test_close_releases_device(self):
        cam = make_camera()
        device = cam.device
        cam.close()
        device.release.assert_called_once()

    def test_isopen_false_after_close(self):
        cam = make_camera()
        cam.close()
        self.assertFalse(cam.isOpen())


class TestProperties(unittest.TestCase):

    def test_width_via_attribute(self):
        cam = make_camera(width=640)
        self.assertEqual(cam.width, 640)

    def test_height_via_attribute(self):
        cam = make_camera(height=480)
        self.assertEqual(cam.height, 480)

    def test_fps_returns_float(self):
        cam = make_camera(fps=30.)
        self.assertIsInstance(cam.fps, float)
        self.assertAlmostEqual(cam.fps, 30.)

    def test_width_setter(self):
        cam = make_camera()
        cam.set('width', 320)
        cam.device.set.assert_any_call(QOpenCVCamera.WIDTH, 320)

    def test_height_setter(self):
        cam = make_camera()
        cam.set('height', 240)
        cam.device.set.assert_any_call(QOpenCVCamera.HEIGHT, 240)

    def test_fps_setter(self):
        cam = make_camera()
        cam.set('fps', 60.)
        cam.device.set.assert_any_call(QOpenCVCamera.FPS, 60.)

    def test_width_setter_emits_shape_changed(self):
        cam = make_camera()
        spy = QtTest.QSignalSpy(cam.shapeChanged)
        cam.set('width', 320)
        self.assertEqual(len(spy), 1)

    def test_height_setter_emits_shape_changed(self):
        cam = make_camera()
        spy = QtTest.QSignalSpy(cam.shapeChanged)
        cam.set('height', 240)
        self.assertEqual(len(spy), 1)

    def test_color_true_when_not_gray(self):
        cam = make_camera(gray=False)
        self.assertTrue(cam.color)

    def test_color_false_when_gray(self):
        cam = make_camera(gray=True)
        self.assertFalse(cam.color)

    def test_color_is_read_only(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
            cam.set('color', False)

    def test_mirrored_setter(self):
        cam = make_camera()
        cam.set('mirrored', True)
        self.assertTrue(cam.mirrored)

    def test_flipped_setter(self):
        cam = make_camera()
        cam.set('flipped', True)
        self.assertTrue(cam.flipped)

    def test_gray_setter(self):
        cam = make_camera()
        cam.set('gray', True)
        self.assertTrue(cam.gray)

    def test_all_properties_registered(self):
        cam = make_camera()
        for name in ('width', 'height', 'fps', 'color',
                     'mirrored', 'flipped', 'gray'):
            self.assertIn(name, cam.properties)


class TestRead(unittest.TestCase):

    def test_read_when_closed_returns_false_none(self):
        cam = make_camera()
        cam.close()
        success, frame = cam.read()
        self.assertFalse(success)
        self.assertIsNone(frame)

    def test_read_returns_frame_on_success(self):
        cam = make_camera()
        success, frame = cam.read()
        self.assertTrue(success)
        self.assertIsInstance(frame, np.ndarray)

    def test_read_colour_frame_converted_to_rgb(self):
        cam = make_camera()
        with patch('cv2.cvtColor', return_value=_FRAME_BGR) as mock_cvt:
            cam.read()
        mock_cvt.assert_called_once()
        _, code = mock_cvt.call_args[0]
        self.assertEqual(code, QOpenCVCamera.BGR2RGB)

    def test_read_colour_frame_converted_to_gray(self):
        cam = make_camera(gray=True)
        with patch('cv2.cvtColor', return_value=_FRAME_GRAY) as mock_cvt:
            cam.read()
        mock_cvt.assert_called_once()
        _, code = mock_cvt.call_args[0]
        self.assertEqual(code, QOpenCVCamera.BGR2GRAY)

    def test_read_grayscale_frame_not_converted(self):
        cam = make_camera(frame=_FRAME_GRAY.copy())
        with patch('cv2.cvtColor') as mock_cvt:
            cam.read()
        mock_cvt.assert_not_called()

    def test_read_mirrored(self):
        cam = make_camera(mirrored=True)
        with patch('cv2.cvtColor', return_value=_FRAME_BGR):
            with patch('cv2.flip', return_value=_FRAME_BGR) as mock_flip:
                cam.read()
        mock_flip.assert_called_once()
        self.assertEqual(mock_flip.call_args[0][1], 1)

    def test_read_flipped(self):
        cam = make_camera(flipped=True)
        with patch('cv2.cvtColor', return_value=_FRAME_BGR):
            with patch('cv2.flip', return_value=_FRAME_BGR) as mock_flip:
                cam.read()
        mock_flip.assert_called_once()
        self.assertEqual(mock_flip.call_args[0][1], 0)

    def test_read_mirrored_and_flipped(self):
        cam = make_camera(mirrored=True, flipped=True)
        with patch('cv2.cvtColor', return_value=_FRAME_BGR):
            with patch('cv2.flip', return_value=_FRAME_BGR) as mock_flip:
                cam.read()
        mock_flip.assert_called_once()
        self.assertEqual(mock_flip.call_args[0][1], -1)

    def test_read_no_flip_when_neither_set(self):
        cam = make_camera()
        with patch('cv2.cvtColor', return_value=_FRAME_BGR):
            with patch('cv2.flip') as mock_flip:
                cam.read()
        mock_flip.assert_not_called()


class TestQOpenCVSource(unittest.TestCase):

    def test_creates_camera_if_none_given(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            src = QOpenCVSource()
        self.assertIsInstance(src.source, QOpenCVCamera)

    def test_uses_provided_camera(self):
        cam = make_camera()
        src = QOpenCVSource(camera=cam)
        self.assertIs(src.source, cam)


if __name__ == '__main__':
    unittest.main()
