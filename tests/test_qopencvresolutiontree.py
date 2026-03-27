'''Unit tests for QOpenCVResolutionTree.'''
import sys
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from pyqtgraph.Qt import QtWidgets
from QVideo.cameras.OpenCV._camera import QOpenCVCamera
from QVideo.cameras.OpenCV._resolution_tree import QOpenCVResolutionTree

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# cameras/OpenCV/__init__.py re-exports QOpenCVResolutionTree (the class), so
# `import QVideo.cameras.OpenCV.QOpenCVResolutionTree` resolves to the class,
# not the module.  Use sys.modules to get the actual module object.
_MODULE = sys.modules['QVideo.cameras.OpenCV._resolution_tree']

_FRAME_BGR = np.zeros((480, 640, 3), dtype=np.uint8)
_RESOLUTIONS_MULTI = [(640, 480), (1280, 720)]


def make_mock_device(width=640, height=480, fps=30., read_ok=True):
    '''Fixed-output device: get() always returns the initial values.'''
    device = MagicMock()
    device.read.return_value = (read_ok, _FRAME_BGR.copy())

    def _get(prop):
        return {QOpenCVCamera.WIDTH: width,
                QOpenCVCamera.HEIGHT: height,
                QOpenCVCamera.FPS: fps}.get(prop, 0)

    device.get.side_effect = _get
    return device


def make_stateful_mock_device(width=640, height=480, fps=30.):
    '''Device that reflects set() calls in subsequent get() calls.

    Simulates V4L2 behaviour: setting width or height resets fps to a
    low fallback value (5.0), as the real V4L2 driver does.
    '''
    device = MagicMock()
    state = [width, height, fps]

    def _get(prop):
        return {QOpenCVCamera.WIDTH: state[0],
                QOpenCVCamera.HEIGHT: state[1],
                QOpenCVCamera.FPS: state[2]}.get(prop, 0)

    def _set(prop, value):
        if prop == QOpenCVCamera.WIDTH:
            state[0] = int(value)
            state[2] = 5.0   # V4L2 resets fps on resolution change
        elif prop == QOpenCVCamera.HEIGHT:
            state[1] = int(value)
            state[2] = 5.0   # V4L2 resets fps on resolution change
        elif prop == QOpenCVCamera.FPS:
            state[2] = float(value)
        return True

    device.read.return_value = (True, _FRAME_BGR.copy())
    device.get.side_effect = _get
    device.set.side_effect = _set
    return device


def make_single_resolution_tree():
    '''Return a tree where probe_resolutions yields only one resolution.'''
    device = make_mock_device()
    with patch('cv2.VideoCapture', return_value=device):
        cam = QOpenCVCamera()
    with patch.object(_MODULE, 'probe_resolutions', return_value=[(640, 480)]):
        tree = QOpenCVResolutionTree(camera=cam)
    return tree, cam, device


def make_multi_resolution_tree(resolutions=None):
    '''Return (tree, camera, device) with a resolution selector.'''
    if resolutions is None:
        resolutions = _RESOLUTIONS_MULTI
    device = make_stateful_mock_device()
    with patch('cv2.VideoCapture', return_value=device):
        cam = QOpenCVCamera()
    with patch.object(_MODULE, 'probe_resolutions', return_value=resolutions):
        tree = QOpenCVResolutionTree(camera=cam)
    return tree, cam, device


def make_clamped_fps_tree():
    '''Return (tree, camera, device) where higher resolution caps fps to 15.

    Simulates real V4L2 behaviour on Ubuntu 24.04: the driver accepts the
    fps set() call but silently clamps to the maximum the sensor supports at
    the requested resolution.
    '''
    _MAX_FPS = {(640, 480): 30.0, (1280, 720): 15.0}
    device = MagicMock()
    state = {'width': 640, 'height': 480, 'fps': 30.0}

    def _get(prop):
        return {QOpenCVCamera.WIDTH: state['width'],
                QOpenCVCamera.HEIGHT: state['height'],
                QOpenCVCamera.FPS: state['fps']}.get(prop, 0)

    def _set(prop, value):
        if prop == QOpenCVCamera.WIDTH:
            state['width'] = int(value)
            state['fps'] = 5.0
        elif prop == QOpenCVCamera.HEIGHT:
            state['height'] = int(value)
            state['fps'] = 5.0
        elif prop == QOpenCVCamera.FPS:
            limit = _MAX_FPS.get((state['width'], state['height']), 30.0)
            state['fps'] = min(float(value), limit)
        return True

    device.read.return_value = (True, _FRAME_BGR.copy())
    device.get.side_effect = _get
    device.set.side_effect = _set

    with patch('cv2.VideoCapture', return_value=device):
        cam = QOpenCVCamera()
    with patch.object(_MODULE, 'probe_resolutions',
                      return_value=[(640, 480), (1280, 720)]):
        tree = QOpenCVResolutionTree(camera=cam)
    return tree, cam, device


class TestQOpenCVResolutionTreeInit(unittest.TestCase):

    def test_creates_successfully_with_provided_camera(self):
        tree, _, _ = make_multi_resolution_tree()
        self.assertIsInstance(tree, QOpenCVResolutionTree)

    def test_uses_provided_camera(self):
        device = make_stateful_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            cam = QOpenCVCamera()
        with patch.object(_MODULE, 'probe_resolutions',
                          return_value=_RESOLUTIONS_MULTI):
            tree = QOpenCVResolutionTree(camera=cam)
        self.assertIs(tree.camera, cam)

    def test_creates_camera_when_none_given(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch.object(_MODULE, 'probe_resolutions',
                              return_value=[(640, 480)]):
                tree = QOpenCVResolutionTree()
        self.assertIsInstance(tree.camera, QOpenCVCamera)

    def test_cameraID_forwarded_when_creating_camera(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device) as mock_cap:
            with patch.object(_MODULE, 'probe_resolutions',
                              return_value=[(640, 480)]):
                QOpenCVResolutionTree(cameraID=2)
        args, _ = mock_cap.call_args
        self.assertEqual(args[0], 2)

    def test_mirrored_forwarded_to_camera(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch.object(_MODULE, 'probe_resolutions',
                              return_value=[(640, 480)]):
                tree = QOpenCVResolutionTree(mirrored=True)
        self.assertTrue(tree.camera.mirrored)

    def test_flipped_forwarded_to_camera(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch.object(_MODULE, 'probe_resolutions',
                              return_value=[(640, 480)]):
                tree = QOpenCVResolutionTree(flipped=True)
        self.assertTrue(tree.camera.flipped)

    def test_gray_forwarded_to_camera(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch.object(_MODULE, 'probe_resolutions',
                              return_value=[(640, 480)]):
                tree = QOpenCVResolutionTree(gray=True)
        self.assertFalse(tree.camera.color)


class TestSingleResolutionFallback(unittest.TestCase):

    def test_width_in_parameters_for_single_resolution(self):
        tree, _, _ = make_single_resolution_tree()
        self.assertIn('width', tree._parameters)

    def test_height_in_parameters_for_single_resolution(self):
        tree, _, _ = make_single_resolution_tree()
        self.assertIn('height', tree._parameters)

    def test_resolution_not_in_parameters_for_single_resolution(self):
        tree, _, _ = make_single_resolution_tree()
        self.assertNotIn('resolution', tree._parameters)


class TestMultiResolutionSelector(unittest.TestCase):

    def setUp(self):
        self.tree, self.cam, self.device = make_multi_resolution_tree()

    def test_resolution_in_parameters(self):
        self.assertIn('resolution', self.tree._parameters)

    def test_width_not_in_parameters(self):
        self.assertNotIn('width', self.tree._parameters)

    def test_height_not_in_parameters(self):
        self.assertNotIn('height', self.tree._parameters)

    def test_resolution_initial_value(self):
        self.assertEqual(self.tree._parameters['resolution'].value(),
                         '640\u00d7480')

    def test_resolution_limits_contain_all_probed(self):
        limits = self.tree._parameters['resolution'].opts.get('limits', [])
        self.assertIn('640\u00d7480', limits)
        self.assertIn('1280\u00d7720', limits)

    def test_resolution_display_strings_use_times_symbol(self):
        self.assertIn('640\u00d7480', self.tree._resolutionMap)
        self.assertIn('1280\u00d7720', self.tree._resolutionMap)

    def test_set_resolution_updates_camera_width(self):
        self.tree._parameters['resolution'].setValue('1280\u00d7720')
        self.assertEqual(self.cam.width, 1280)

    def test_set_resolution_updates_camera_height(self):
        self.tree._parameters['resolution'].setValue('1280\u00d7720')
        self.assertEqual(self.cam.height, 720)

    def test_set_width_updates_resolution_selector(self):
        self.cam.set('width', 1280)
        self.cam.set('height', 720)
        self.tree.set('width', 1280)
        self.assertEqual(self.tree._parameters['resolution'].value(),
                         '1280\u00d7720')

    def test_set_height_updates_resolution_selector(self):
        self.cam.set('width', 1280)
        self.cam.set('height', 720)
        self.tree.set('height', 720)
        self.assertEqual(self.tree._parameters['resolution'].value(),
                         '1280\u00d7720')

    def test_resolution_position_before_fps(self):
        params = list(self.tree._parameters.keys())
        if 'fps' in params:
            self.assertLess(params.index('resolution'), params.index('fps'))

    def test_fps_preserved_after_resolution_change(self):
        '''V4L2 resets fps when resolution changes; the tree must restore it.'''
        initial_fps = self.cam.fps
        self.tree._parameters['resolution'].setValue('1280\u00d7720')
        self.assertEqual(self.cam.fps, initial_fps)

    def test_fps_display_updated_when_driver_clamps_fps(self):
        '''When V4L2 silently caps fps at higher resolution, the tree display
        must show the clamped value, not the pre-change requested value.'''
        tree, cam, _ = make_clamped_fps_tree()
        self.assertEqual(tree._parameters['fps'].value(), 30.0)
        tree._parameters['resolution'].setValue('1280\u00d7720')
        self.assertEqual(tree._parameters['fps'].value(), cam.fps)  # 15.0

    def test_fps_restored_after_first_frame_when_source_running(self):
        '''When the source is running the fps restore is deferred until the
        first newFrame signal so that the V4L2 format change is committed
        before VIDIOC_S_PARM is issued.'''
        tree, cam, _ = make_multi_resolution_tree()
        # Simulate a running source by making isRunning() return True.
        tree.source.isRunning = lambda: True
        initial_fps = cam.fps
        tree._parameters['resolution'].setValue('1280\u00d7720')
        # fps must NOT be restored yet (deferred)
        self.assertNotEqual(cam.fps, initial_fps)
        # Simulate the first frame arriving at the new resolution
        tree.source.newFrame.emit(np.zeros((720, 1280, 3), dtype=np.uint8))
        # fps must now be restored
        self.assertEqual(cam.fps, initial_fps)

    def test_unknown_resolution_does_not_crash(self):
        self.tree.set('width', 9999)


if __name__ == '__main__':
    unittest.main()
