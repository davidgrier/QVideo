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
    '''Return a mock device that remembers the width, height, and fps set.'''
    device = MagicMock()
    device.read.return_value = (read_ok, _FRAME_BGR.copy())
    state = {QOpenCVCamera.WIDTH: width,
             QOpenCVCamera.HEIGHT: height,
             QOpenCVCamera.FPS: fps}

    def _set(prop, value):
        if prop in state:
            state[prop] = value
        return True

    device.get.side_effect = lambda prop: state.get(prop, 0)
    device.set.side_effect = _set
    return device


def make_camera(formats=None, size=(640, 480), **kwargs):
    '''Return a QOpenCVCamera with a mocked device.

    Parameters
    ----------
    formats : list or None
        Format list returned by ``probe_formats``.
        Defaults to ``_FORMATS``.
    size : tuple[int, int]
        ``(width, height)`` at which the mocked device opens.
    '''
    if formats is None:
        formats = _FORMATS
    device = make_mock_device(*size)
    with patch('cv2.VideoCapture', return_value=device):
        with patch('QVideo.cameras.OpenCV._camera.configure'):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                       return_value=formats):
                cam = QOpenCVCamera(**kwargs)
    return cam


def make_tree(formats=None, size=(640, 480), **kwargs):
    '''Return a ``(QOpenCVTree, QOpenCVCamera)`` pair with a mocked device.'''
    cam = make_camera(formats=formats, size=size)
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

    def test_fps_enabled_when_no_formats(self):
        tree, _ = make_tree(formats=[])
        if 'fps' in tree._parameters:
            self.assertTrue(tree._parameters['fps'].opts.get('enabled', True))

    def test_initial_value_matches_every_camera_resolution(self):
        '''The dropdown shows the format the camera is actually using, not
        merely the first one.'''
        for w, h, _min, fps in _FORMATS:
            with self.subTest(size=(w, h)):
                tree, cam = make_tree(size=(w, h))
                self.assertEqual(tree._parameters['resolution'].value(),
                                 f'{w}\u00d7{h} @ {fps:.0f} Hz')

    def test_values_are_the_labels_the_camera_uses(self):
        tree, cam = make_tree()
        limits = tree._parameters['resolution'].opts.get('limits')
        self.assertEqual(list(limits), list(cam._formatLabels))
        self.assertIn(tree._parameters['resolution'].value(), limits)


class TestResolutionSync(unittest.TestCase):
    '''Test that selecting a resolution entry updates the camera.'''

    LABEL = '1280\u00d7720 @ 30 Hz'

    def _device_calls(self, cam, prop):
        return [c.args[1] for c in cam._device.set.call_args_list
                if c.args[0] == prop]

    def test_selecting_sets_width(self):
        tree, cam = make_tree()
        cam._device.set.reset_mock()
        tree._parameters['resolution'].setValue(self.LABEL)
        self.assertIn(1280, self._device_calls(cam, QOpenCVCamera.WIDTH))

    def test_selecting_sets_height(self):
        tree, cam = make_tree()
        cam._device.set.reset_mock()
        tree._parameters['resolution'].setValue(self.LABEL)
        self.assertIn(720, self._device_calls(cam, QOpenCVCamera.HEIGHT))

    def test_selecting_sets_fps(self):
        tree, cam = make_tree()
        cam._device.set.reset_mock()
        tree._parameters['resolution'].setValue(self.LABEL)
        self.assertIn(30., self._device_calls(cam, QOpenCVCamera.FPS))

    def test_selecting_updates_the_width_and_height_fields(self):
        tree, _ = make_tree()
        tree._parameters['resolution'].setValue(self.LABEL)
        self.assertEqual(tree._parameters['width'].value(), 1280)
        self.assertEqual(tree._parameters['height'].value(), 720)

    def test_selection_ignored_when_ignoreSync_set(self):
        tree, cam = make_tree()
        cam._device.set.reset_mock()
        tree._ignoreSync = True
        tree._parameters['resolution'].setValue(self.LABEL)
        self.assertEqual(self._device_calls(cam, QOpenCVCamera.WIDTH), [])

    def test_non_resolution_changes_forwarded_to_base(self):
        '''Non-resolution changes reach the camera via the base _sync path.'''
        tree, cam = make_tree()
        cam._device.set.reset_mock()
        param = MagicMock()
        param.name.return_value = 'mirrored'
        changes = [(param, 'value', True)]
        tree._sync(None, changes)
        self.assertTrue(cam.mirrored)

    def test_unrelated_change_does_not_reset_the_resolution(self):
        '''Syncing other properties must leave the dropdown on the
        camera's current resolution (it used to jump to the first entry).'''
        tree, cam = make_tree(size=(1280, 720))
        param = MagicMock()
        param.name.return_value = 'mirrored'
        tree._sync(None, [(param, 'value', True)])
        self.assertEqual(tree._parameters['resolution'].value(), self.LABEL)

    def test_disabling_fields_at_construction_keeps_the_resolution(self):
        '''Building the tree disables width, height, and fps; that must not
        overwrite the dropdown.'''
        tree, _ = make_tree(size=(1920, 1080))
        self.assertEqual(tree._parameters['resolution'].value(),
                         '1920\u00d71080 @ 15 Hz')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
