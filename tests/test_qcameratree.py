'''Unit tests for QCameraTree.'''
import unittest
from unittest.mock import patch, MagicMock
from qtpy import QtGui, QtWidgets
from QVideo.lib.QCameraTree import QCameraTree
from QVideo.cameras.Noise._camera import QNoiseCamera, QNoiseSource


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


class TestQCameraTreeTitle(unittest.TestCase):

    def test_title_uses_class_name_when_model_name_is_none(self):
        cam = make_camera()
        self.assertIsNone(cam.model_name)
        tree = make_tree(source=make_source(cam))
        self.assertEqual(tree._tree.name(), cam.name)

    def test_title_uses_model_name_when_set(self):
        cam = make_camera()
        cam._modelName = 'FaceTime HD Camera'
        tree = make_tree(source=make_source(cam))
        self.assertEqual(tree._tree.name(), 'FaceTime HD Camera')

    def test_title_falls_back_to_class_name_for_empty_model_name(self):
        cam = make_camera()
        cam._modelName = ''
        tree = make_tree(source=make_source(cam))
        self.assertEqual(tree._tree.name(), cam.name)


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
        '''_sync sets _ignoreSync to avoid re-entrant loops.'''
        tree = make_tree()
        # If this call returns without recursion error, the guard works
        tree._parameters['width'].setValue(320)


class TestQCameraTreeDefaultDescriptionNone(unittest.TestCase):

    def test_skips_properties_with_none_getter(self):
        '''_defaultDescription omits entries whose getter returns None.'''
        cam = make_camera()
        cam._properties['_fake'] = {'getter': lambda: None, 'setter': None}
        try:
            desc = QCameraTree._defaultDescription(cam)
            names = [e['name'] for e in desc]
            self.assertNotIn('_fake', names)
        finally:
            del cam._properties['_fake']


class TestQCameraTreeCloseEvent(unittest.TestCase):

    def test_close_event_stops_running_source(self):
        tree = make_tree()
        tree.start()
        event = QtGui.QCloseEvent()
        tree.closeEvent(event)
        self.assertFalse(tree.source.isRunning())

    def test_close_event_safe_when_not_running(self):
        tree = make_tree()
        event = QtGui.QCloseEvent()
        tree.closeEvent(event)  # should not raise


class TestQCameraTreeSyncGuard(unittest.TestCase):

    def test_sync_returns_early_when_ignoreSync_set(self):
        '''_sync short-circuits when _ignoreSync is True.'''
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        tree._ignoreSync = True
        original_width = cam.width
        # Calling _sync directly with a value change should be ignored
        param = tree._parameters['width']
        tree._sync(None, [(param, 'value', 9999)])
        self.assertEqual(cam.width, original_width)
        tree._ignoreSync = False


class TestQCameraTreeCustomDescription(unittest.TestCase):

    def test_accepts_custom_description(self):
        '''Passing a description skips _defaultDescription (covers 99→101 branch).'''
        desc = [{'name': 'width', 'type': 'int', 'value': 640, 'default': 640}]
        source = make_source()
        tree = QCameraTree(source, description=desc)
        self.assertIn('width', tree._parameters)

    def test_custom_description_excludes_undescribed_properties(self):
        desc = [{'name': 'width', 'type': 'int', 'value': 640, 'default': 640}]
        source = make_source()
        tree = QCameraTree(source, description=desc)
        self.assertNotIn('height', tree._parameters)


class TestQCameraTreeSyncNonValueChange(unittest.TestCase):

    def test_sync_ignores_non_value_changes(self):
        '''_sync skips changes where change != "value" (covers 129→128 branch).'''
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        original_width = cam.width
        param = tree._parameters['width']
        tree._sync(None, [(param, 'options', 9999)])
        self.assertEqual(cam.width, original_width)


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


class TestQCameraTreeUpdateStepUnit(unittest.TestCase):
    '''Direct unit tests for the static _updateStep helper.'''

    def test_skips_non_float_type(self):
        param = MagicMock()
        param.opts = {'type': 'int'}
        QCameraTree._updateStep(param)
        param.setOpts.assert_not_called()

    def test_skips_zero_value(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = 0.0
        QCameraTree._updateStep(param)
        param.setOpts.assert_not_called()

    def test_skips_non_numeric_value(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = 'not-a-number'
        QCameraTree._updateStep(param)
        param.setOpts.assert_not_called()

    def test_step_is_tenth_of_order_of_magnitude(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = 250.0
        QCameraTree._updateStep(param)
        param.setOpts.assert_called_once_with(step=10.0)

    def test_step_scales_for_small_values(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = 0.0005
        QCameraTree._updateStep(param)
        param.setOpts.assert_called_once_with(step=1e-5)

    def test_step_uses_magnitude_for_negative_values(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = -250.0
        QCameraTree._updateStep(param)
        param.setOpts.assert_called_once_with(step=10.0)


class TestQCameraTreeAdaptiveStepIntegration(unittest.TestCase):
    '''End-to-end coverage of adaptive stepping through a real tree.

    Uses QNoiseCamera.fps, a genuine registered float property, so the
    _sync/camera.set round trip exercises the real code path rather
    than a property name unknown to the camera.
    '''

    def test_initial_step_set_on_tree_creation(self):
        tree = make_tree()
        step = tree._parameters['fps'].opts['step']
        self.assertAlmostEqual(step, 1.0)  # fps defaults to 30.0

    def test_step_rescales_when_tree_value_edited(self):
        tree = make_tree()
        tree._parameters['fps'].setValue(0.001)
        step = tree._parameters['fps'].opts['step']
        self.assertAlmostEqual(step, 1e-4)

    def test_step_rescales_via_tree_set(self):
        tree = make_tree()
        tree.set('fps', 5000.0)
        step = tree._parameters['fps'].opts['step']
        self.assertAlmostEqual(step, 100.0)


if __name__ == '__main__':
    unittest.main()
