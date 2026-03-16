'''Unit tests for QOpenCVTree.'''
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from pyqtgraph.Qt import QtWidgets
from QVideo.cameras.OpenCV.QOpenCVCamera import QOpenCVCamera
from QVideo.cameras.OpenCV.QOpenCVTree import QOpenCVTree


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME_BGR = np.zeros((480, 640, 3), dtype=np.uint8)


def make_mock_device(width=640, height=480, fps=30., read_ok=True):
    device = MagicMock()
    device.read.return_value = (read_ok, _FRAME_BGR.copy())

    def _get(prop):
        return {QOpenCVCamera.WIDTH: width,
                QOpenCVCamera.HEIGHT: height,
                QOpenCVCamera.FPS: fps}.get(prop, 0)

    device.get.side_effect = _get
    return device


def make_camera(**kwargs):
    device = make_mock_device()
    with patch('cv2.VideoCapture', return_value=device):
        cam = QOpenCVCamera(**kwargs)
    return cam


class TestQOpenCVTreeInit(unittest.TestCase):

    def test_creates_successfully_with_provided_camera(self):
        cam = make_camera()
        tree = QOpenCVTree(camera=cam)
        self.assertIsInstance(tree, QOpenCVTree)

    def test_uses_provided_camera(self):
        cam = make_camera()
        tree = QOpenCVTree(camera=cam)
        self.assertIs(tree.camera, cam)

    def test_creates_camera_when_none_given(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            tree = QOpenCVTree()
        self.assertIsInstance(tree.camera, QOpenCVCamera)

    def test_cameraID_forwarded_when_creating_camera(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device) as mock_cap:
            QOpenCVTree(cameraID=2)
        args, _ = mock_cap.call_args
        self.assertEqual(args[0], 2)


if __name__ == '__main__':
    unittest.main()
