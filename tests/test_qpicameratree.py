'''Unit tests for QPicameraTree.'''
import sys
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtWidgets

from QVideo.cameras.Picamera._camera import QPicamera
from QVideo.cameras.Picamera._tree import QPicameraTree
from QVideo.lib import QCameraTree

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_CAMERA_MODULE = sys.modules['QVideo.cameras.Picamera._camera']
_TREE_MODULE = sys.modules['QVideo.cameras.Picamera._tree']

_FRAME_RGB = np.zeros((960, 1280, 3), dtype=np.uint8)

_CAMERA_CONTROLS = {
    'AeEnable':            (False, True,      True),
    'AwbEnable':           (False, True,      True),
    'Brightness':          (-1.0,  1.0,       0.0),
    'Contrast':            (0.0,   32.0,      1.0),
    'Saturation':          (0.0,   32.0,      1.0),
    'Sharpness':           (0.0,   16.0,      1.0),
    'ExposureTime':        (100,   1000000,   10000),
    'AnalogueGain':        (1.0,   16.0,      1.0),
    'FrameDurationLimits': (33333, 120000000, (33333, 33333)),
}

_METADATA = {
    'AeEnable':      True,
    'AwbEnable':     True,
    'Brightness':    0.0,
    'Contrast':      1.0,
    'Saturation':    1.0,
    'Sharpness':     1.0,
    'ExposureTime':  10000,
    'AnalogueGain':  1.0,
    'FrameDuration': 33333,
}


def make_mock_device():
    device = MagicMock()
    device.camera_controls = _CAMERA_CONTROLS.copy()
    device.camera_config = {'main': {'size': (1280, 960), 'format': 'RGB888'}}
    request = MagicMock()
    request.make_array.return_value = _FRAME_RGB.copy()
    device.capture_request.return_value = request
    device.capture_metadata.return_value = _METADATA.copy()
    return device


def make_camera():
    device = make_mock_device()
    with patch.object(_CAMERA_MODULE, 'Picamera2', return_value=device):
        cam = QPicamera()
    return cam, device


class TestQPicameraTreeWithCamera(unittest.TestCase):

    def setUp(self):
        self.cam, _ = make_camera()
        self.tree = QPicameraTree(camera=self.cam)

    def tearDown(self):
        self.cam.close()

    def test_creates_successfully(self):
        self.assertIsInstance(self.tree, QPicameraTree)

    def test_is_subclass_of_qcameratree(self):
        self.assertIsInstance(self.tree, QCameraTree)

    def test_width_parameter_disabled(self):
        param = self.tree._parameters.get('width')
        if param is not None:
            self.assertFalse(param.opts.get('enabled', True))

    def test_height_parameter_disabled(self):
        param = self.tree._parameters.get('height')
        if param is not None:
            self.assertFalse(param.opts.get('enabled', True))


class TestQPicameraTreeWithoutCamera(unittest.TestCase):

    def test_creates_camera_when_none_given(self):
        device = make_mock_device()
        with patch.object(_CAMERA_MODULE, 'Picamera2', return_value=device):
            tree = QPicameraTree()
        self.assertIsInstance(tree, QPicameraTree)
        tree.source.source.close()

    def test_forwards_camera_id(self):
        device = make_mock_device()
        with patch.object(_CAMERA_MODULE, 'Picamera2', return_value=device) as mock_cls:
            QPicameraTree(cameraID=1)
        mock_cls.assert_called_once_with(camera_num=1)

    def test_forwards_width(self):
        device = make_mock_device()
        device.camera_config = {'main': {'size': (640, 480), 'format': 'RGB888'}}
        with patch.object(_CAMERA_MODULE, 'Picamera2', return_value=device):
            tree = QPicameraTree(width=640, height=480)
        self.assertIsInstance(tree, QPicameraTree)
        tree.source.source.close()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
