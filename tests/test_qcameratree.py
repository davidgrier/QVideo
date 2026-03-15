'''Unit tests for QCameraTree.'''
import unittest
from unittest.mock import patch
from pyqtgraph.Qt import QtWidgets
from QVideo.lib.QCameraTree import QCameraTree
from QVideo.cameras.Noise.QNoiseCamera import QNoiseCamera, QNoiseSource


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_camera():
    return QNoiseCamera()


def make_source(camera=None):
    camera = camera or make_camera()
    return QNoiseSource(camera=camera)


def make_tree(source=None):
    source = source or make_source()
    return QCameraTree(source)


class TestQCameraTreeInit(unittest.TestCase):

    def test_raises_if_source_not_open(self):
        cam = make_camera()
        cam.close()
        source = QNoiseSource(camera=cam)
        with self.assertRaises(RuntimeError):
            QCameraTree(source)

    def test_creates_successfully_with_open_source(self):
        tree = make_tree()
        self.assertIsInstance(tree, QCameraTree)

    def test_camera_property_returns_noise_camera(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        self.assertIs(tree.camera, cam)

    def test_source_property_returns_source(self):
        source = make_source()
        tree = QCameraTree(source)
        self.assertIs(tree.source, source)

    def test_accepts_bare_camera(self):
        cam = make_camera()
        tree = QCameraTree(cam)
        self.assertIsInstance(tree, QCameraTree)


class TestQCameraTreeDefaultDescription(unittest.TestCase):

    def test_all_camera_properties_appear_in_tree(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        for name in cam.properties:
            self.assertIn(name, tree._parameters)

    def test_readonly_property_is_disabled_in_tree(self):
        '''QNoiseCamera.color has setter=None and should appear disabled.'''
        tree = make_tree()
        color_param = tree._parameters.get('color')
        self.assertIsNotNone(color_param)
        self.assertFalse(color_param.opts.get('enabled', True))

    def test_writable_property_is_enabled_in_tree(self):
        tree = make_tree()
        width_param = tree._parameters.get('width')
        self.assertIsNotNone(width_param)
        self.assertTrue(width_param.opts.get('enabled', True))


class TestQCameraTreeGet(unittest.TestCase):

    def test_get_returns_current_value(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        self.assertEqual(tree.get('width'), cam.width)

    def test_get_unknown_key_returns_none(self):
        tree = make_tree()
        with self.assertLogs('QVideo.lib.QCameraTree', level='WARNING'):
            result = tree.get('nonexistent')
        self.assertIsNone(result)


class TestQCameraTreeSet(unittest.TestCase):

    def test_set_updates_tree_parameter(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        tree.set('width', 320)
        self.assertEqual(tree._parameters['width'].value(), 320)

    def test_set_unknown_key_logs_warning(self):
        tree = make_tree()
        with self.assertLogs('QVideo.lib.QCameraTree', level='WARNING'):
            tree.set('nonexistent', 42)


class TestQCameraTreeSync(unittest.TestCase):

    def test_tree_change_updates_camera(self):
        '''Changing a parameter in the tree calls camera.set().'''
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        tree._parameters['width'].setValue(320)
        self.assertEqual(cam.width, 320)

    def test_set_does_not_cause_infinite_loop(self):
        '''_sync sets _ignore_sync to avoid re-entrant loops.'''
        tree = make_tree()
        # If this call returns without recursion error, the guard works
        tree._parameters['width'].setValue(320)


class TestQCameraTreeStartStop(unittest.TestCase):

    def test_start_returns_self(self):
        tree = make_tree()
        result = tree.start()
        self.assertIs(result, tree)
        tree.stop()

    def test_stop_when_not_running_is_safe(self):
        tree = make_tree()
        tree.stop()  # source never started — should not raise

    def test_stop_joins_running_source(self):
        tree = make_tree()
        tree.start()
        tree.stop()
        self.assertFalse(tree.source.isRunning())


if __name__ == '__main__':
    unittest.main()
