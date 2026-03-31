'''Unit tests for QOpenCVTree.'''
import unittest
from unittest.mock import MagicMock, patch, call
import numpy as np
from qtpy import QtWidgets
from QVideo.cameras.OpenCV._camera import QOpenCVCamera
from QVideo.cameras.OpenCV._tree import QOpenCVTree

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME_BGR = np.zeros((480, 640, 3), dtype=np.uint8)

_FORMATS = [
    (640,  480,  5., 30.),
    (1280, 720,  5., 30.),
    (1920, 1080, 5., 15.),
]


def make_mock_device(width=640, height=480, fps=30., read_ok=True):
    device = MagicMock()
    device.read.return_value = (read_ok, _FRAME_BGR.copy())

    def _get(prop):
        return {QOpenCVCamera.WIDTH: width,
                QOpenCVCamera.HEIGHT: height,
                QOpenCVCamera.FPS: fps}.get(prop, 0)

    device.get.side_effect = _get
    device.set.return_value = True
    return device


def make_camera(formats=None, **kwargs):
    '''Return a QOpenCVCamera with a mocked device.

    Parameters
    ----------
    formats : list or None
        Format list returned by ``probe_formats``.
        Defaults to ``_FORMATS``.
    '''
    if formats is None:
        formats = _FORMATS
    device = make_mock_device()
    with patch('cv2.VideoCapture', return_value=device):
        with patch('QVideo.cameras.OpenCV._camera.configure'):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                       return_value=formats):
                cam = QOpenCVCamera(**kwargs)
    return cam


def make_tree(formats=None, **kwargs):
    '''Return a ``(QOpenCVTree, QOpenCVCamera)`` pair with a mocked device.'''
    cam = make_camera(formats=formats)
    tree = QOpenCVTree(camera=cam, **kwargs)
    return tree, cam


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
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                              return_value=[(640, 480, 1., 30.)]):
                tree = QOpenCVTree()
        self.assertIsInstance(tree.camera, QOpenCVCamera)

    def test_cameraID_forwarded_when_creating_camera(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device) as mock_cap:
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                              return_value=[(640, 480, 1., 30.)]):
                QOpenCVTree(cameraID=2)
        args, _ = mock_cap.call_args
        self.assertEqual(args[0], 2)

    def test_mirrored_forwarded_to_camera(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                              return_value=[(640, 480, 1., 30.)]):
                tree = QOpenCVTree(mirrored=True)
        self.assertTrue(tree.camera.mirrored)

    def test_flipped_forwarded_to_camera(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                              return_value=[(640, 480, 1., 30.)]):
                tree = QOpenCVTree(flipped=True)
        self.assertTrue(tree.camera.flipped)

    def test_gray_forwarded_to_camera(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                              return_value=[(640, 480, 1., 30.)]):
                tree = QOpenCVTree(gray=True)
        self.assertFalse(tree.camera.color)

    def test_width_in_parameters(self):
        tree, _ = make_tree()
        self.assertIn('width', tree._parameters)

    def test_height_in_parameters(self):
        tree, _ = make_tree()
        self.assertIn('height', tree._parameters)


class TestResolutionEnum(unittest.TestCase):

    def test_resolution_in_parameters_when_formats_available(self):
        tree, _ = make_tree()
        self.assertIn('resolution', tree._parameters)

    def test_resolution_not_in_parameters_when_no_formats(self):
        tree, _ = make_tree(formats=[])
        self.assertNotIn('resolution', tree._parameters)

    def test_width_disabled(self):
        tree, _ = make_tree()
        self.assertFalse(tree._parameters['width'].opts.get('enabled', True))

    def test_height_disabled(self):
        tree, _ = make_tree()
        self.assertFalse(tree._parameters['height'].opts.get('enabled', True))

    def test_fps_disabled_when_formats_available(self):
        tree, _ = make_tree()
        if 'fps' in tree._parameters:
            self.assertFalse(tree._parameters['fps'].opts.get('enabled', True))

    def test_resolution_labels_contain_dimensions(self):
        tree, _ = make_tree()
        limits = tree._parameters['resolution'].opts.get('limits', {})
        for label in limits:
            self.assertIn('×', label)

    def test_resolution_labels_contain_fps(self):
        tree, _ = make_tree()
        limits = tree._parameters['resolution'].opts.get('limits', {})
        for label in limits:
            self.assertIn('@', label)

    def test_number_of_entries_matches_formats(self):
        tree, _ = make_tree()
        limits = tree._parameters['resolution'].opts.get('limits', {})
        self.assertEqual(len(limits), len(_FORMATS))

    def test_initial_value_matches_current_camera_resolution(self):
        '''Initial enum value matches the camera's current width/height.'''
        cam = make_camera()
        # Camera opens at 640×480 (mock device default)
        tree = QOpenCVTree(camera=cam)
        w, h, _fps = tree._parameters['resolution'].value()
        self.assertEqual(w, cam.width)
        self.assertEqual(h, cam.height)

    def test_enum_values_are_tuples(self):
        tree, _ = make_tree()
        limits = tree._parameters['resolution'].opts.get('limits', {})
        for val in limits.values():
            self.assertIsInstance(val, tuple)
            self.assertEqual(len(val), 3)


class TestResolutionSync(unittest.TestCase):
    '''Test that selecting a resolution entry updates the camera.'''

    def _make_resolution_change(self, tree, w, h, fps):
        '''Simulate a resolution parameter change via _sync.'''
        param = MagicMock()
        param.name.return_value = 'resolution'
        changes = [(param, 'value', (w, h, float(fps)))]
        tree._sync(None, changes)

    def test_sync_sets_width(self):
        tree, cam = make_tree()
        cam.device.set.reset_mock()
        self._make_resolution_change(tree, 1280, 720, 30.)
        cam.device.set.assert_any_call(QOpenCVCamera.WIDTH, 1280)

    def test_sync_sets_height(self):
        tree, cam = make_tree()
        cam.device.set.reset_mock()
        self._make_resolution_change(tree, 1280, 720, 30.)
        cam.device.set.assert_any_call(QOpenCVCamera.HEIGHT, 720)

    def test_sync_sets_fps(self):
        tree, cam = make_tree()
        cam.device.set.reset_mock()
        self._make_resolution_change(tree, 1280, 720, 30.)
        cam.device.set.assert_any_call(QOpenCVCamera.FPS, 30.)

    def test_sync_ignored_when_ignoreSync_set(self):
        tree, cam = make_tree()
        cam.device.set.reset_mock()
        tree._ignoreSync = True
        self._make_resolution_change(tree, 1280, 720, 30.)
        # No device.set calls should have occurred
        width_calls = [c for c in cam.device.set.call_args_list
                       if c.args[0] == QOpenCVCamera.WIDTH]
        self.assertEqual(width_calls, [])

    def test_non_resolution_changes_forwarded_to_base(self):
        '''Non-resolution changes reach the camera via the base _sync path.'''
        tree, cam = make_tree()
        cam.device.set.reset_mock()
        param = MagicMock()
        param.name.return_value = 'mirrored'
        changes = [(param, 'value', True)]
        tree._sync(None, changes)
        self.assertTrue(cam.mirrored)


if __name__ == '__main__':
    unittest.main()
