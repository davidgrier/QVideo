'''Unit tests for QGenicamCamera and QGenicamSource.'''
import subprocess
import sys
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from pyqtgraph.Qt import QtWidgets, QtTest


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# ---------------------------------------------------------------------------
# Stub the optional genicam / harvesters packages before importing the module
# under test.  Real subclassable types let isinstance() checks work.
# ---------------------------------------------------------------------------

class _IValue:                pass
class _ICategory(_IValue):    pass
class _ICommand(_IValue):     pass
class _IEnumeration(_IValue): pass
class _IBoolean(_IValue):     pass
class _IInteger(_IValue):     pass
class _IFloat(_IValue):       pass
class _IString(_IValue):      pass


class _EAccessMode:
    RW = 'RW'
    RO = 'RO'
    WO = 'WO'
    NI = 'NI'


class _TimeoutException(Exception):
    pass


_mock_genapi = MagicMock()
_mock_genapi.IValue       = _IValue
_mock_genapi.ICategory    = _ICategory
_mock_genapi.ICommand     = _ICommand
_mock_genapi.IEnumeration = _IEnumeration
_mock_genapi.IBoolean     = _IBoolean
_mock_genapi.IInteger     = _IInteger
_mock_genapi.IFloat       = _IFloat
_mock_genapi.IString      = _IString
_mock_genapi.EAccessMode  = _EAccessMode


class _EVisibility(int):
    '''Minimal stand-in for genicam.genapi.EVisibility.

    Must be a real Python type so that @pyqtProperty(EVisibility) in
    QGenicamTree does not raise TypeError at class-definition time.
    '''


_EVisibility.Beginner  = _EVisibility(0)
_EVisibility.Expert    = _EVisibility(1)
_EVisibility.Guru      = _EVisibility(2)
_EVisibility.Invisible = _EVisibility(99)

_mock_genapi.EVisibility  = _EVisibility
# IProperty union — mirrors the camera module definition
_mock_genapi.IProperty = (_IEnumeration, _IBoolean, _IInteger, _IFloat, _IString)

_mock_gentl                  = MagicMock()
_mock_gentl.TimeoutException = _TimeoutException

_mock_harvesters_core = MagicMock()
_mock_harvesters      = MagicMock()
_mock_harvesters.core = _mock_harvesters_core

for _name, _mod in [('harvesters',      _mock_harvesters),
                    ('harvesters.core', _mock_harvesters_core),
                    ('genicam',         MagicMock()),
                    ('genicam.genapi',  _mock_genapi),
                    ('genicam.gentl',   _mock_gentl)]:
    sys.modules.setdefault(_name, _mod)


from QVideo.cameras.Genicam.QGenicamCamera import QGenicamCamera, QGenicamSource
# Retrieve the module object directly — the `import ... as` form resolves
# through attribute access and lands on the class (shadowed by __init__.py).
_cam_module = sys.modules['QVideo.cameras.Genicam.QGenicamCamera']

# Use the exact class objects that the loaded camera module references.
# If test_qgenicamtree.py ran first it may have placed different stubs in
# sys.modules; reading back from the module ensures isinstance() checks in
# the camera code and in our helpers agree on the same type objects.
_IValue       = _cam_module.IValue
_ICategory    = _cam_module.ICategory
_ICommand     = _cam_module.ICommand
_IEnumeration = _cam_module.IEnumeration
_IBoolean     = _cam_module.IBoolean
_IInteger     = _cam_module.IInteger
_IFloat       = _cam_module.IFloat
_IString      = _cam_module.IString
_EAccessMode  = _cam_module.EAccessMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRODUCER = '/fake/producer.cti'


class _ConcreteCamera(QGenicamCamera):
    '''Minimal concrete subclass with a fixed producer for testing.'''
    producer = PRODUCER


def _make_node_map(model_name='TestCamera'):
    nm = MagicMock()
    nm.DeviceModelName.value = model_name
    nm.has_node.return_value = True
    root = MagicMock(spec=_ICategory)
    root.features = []
    nm.get_node.return_value = root
    return nm


def _make_device(node_map=None, is_valid=True):
    if node_map is None:
        node_map = _make_node_map()
    device = MagicMock()
    device.is_valid.return_value = is_valid
    device.is_acquiring.return_value = True
    device.remote_device.node_map = node_map
    image = MagicMock()
    image.height = 480
    image.width = 640
    image.num_components_per_pixel = 1
    image.data = np.zeros(480 * 640, dtype=np.uint8)
    buf = MagicMock()
    buf.payload.components = [image]
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=buf)
    cm.__exit__ = MagicMock(return_value=False)
    device.fetch.return_value = cm
    return device


def make_camera(cameraID=0, device=None):
    '''Return (camera, harvester_instance, device) with mocked hardware.'''
    if device is None:
        device = _make_device()
    harvester = MagicMock()
    harvester.create.return_value = device
    with patch.object(_cam_module, 'Harvester', return_value=harvester):
        cam = _ConcreteCamera(cameraID=cameraID)
    return cam, harvester, device


def make_camera_with_node(feature, **kwargs):
    '''Return (camera, harvester, device) with feature pre-registered.

    The feature is placed in root.features so that _initialize registers
    it via registerProperty / registerMethod.
    '''
    device = _make_device()
    root = MagicMock(spec=_ICategory)
    root.features = [feature]
    device.remote_device.node_map.get_node.return_value = root
    cam, harvester, device = make_camera(device=device, **kwargs)
    return cam, harvester, device


def _make_feature(ftype, name='Prop', mode=_EAccessMode.RW, **kw):
    '''Return a MagicMock that passes isinstance(f, ftype) checks.

    Using spec= would restrict attribute access to members defined on the
    stub type, blocking .node, .value, etc.  Setting __class__ makes
    isinstance work without restricting the mock's attribute space.
    '''
    f = MagicMock()
    f.__class__ = ftype
    f.node = MagicMock()
    f.node.name = name
    f.node.get_access_mode.return_value = mode
    for k, v in kw.items():
        setattr(f, k, v)
    return f


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------

class TestInit(unittest.TestCase):

    def test_producer_class_attribute(self):
        cam, _, _ = make_camera()
        self.assertEqual(cam.producer, PRODUCER)

    def test_raises_when_producer_is_none(self):
        with self.assertRaises(TypeError):
            QGenicamCamera()

    def test_camera_id_default_zero(self):
        cam, _, _ = make_camera()
        self.assertEqual(cam.cameraID, 0)

    def test_custom_camera_id(self):
        cam, _, _ = make_camera(cameraID=2)
        self.assertEqual(cam.cameraID, 2)

    def test_opens_on_init(self):
        cam, _, _ = make_camera()
        self.assertTrue(cam.isOpen())


# ---------------------------------------------------------------------------
# TestInitialize
# ---------------------------------------------------------------------------

class TestInitialize(unittest.TestCase):

    def test_harvester_add_file_called_with_producer(self):
        _, h, _ = make_camera()
        h.add_file.assert_called_once_with(PRODUCER)

    def test_harvester_update_called(self):
        _, h, _ = make_camera()
        h.update.assert_called_once()

    def test_harvester_create_called_with_camera_id(self):
        _, h, _ = make_camera(cameraID=1)
        h.create.assert_called_once_with(1)

    def test_device_start_called(self):
        _, _, device = make_camera()
        device.start.assert_called()

    def test_module_raises_import_error_without_dependencies(self):
        '''Module import raises ImportError with an install hint when
        harvesters/genicam are absent.
        '''
        script = (
            "import builtins, sys\n"
            "_real_import = builtins.__import__\n"
            "def _blocking_import(name, *args, **kwargs):\n"
            "    if name in ('harvesters', 'harvesters.core',\n"
            "                'genicam', 'genicam.genapi', 'genicam.gentl'):\n"
            "        raise ImportError(f'blocked: {name}')\n"
            "    return _real_import(name, *args, **kwargs)\n"
            "builtins.__import__ = _blocking_import\n"
            "try:\n"
            "    from QVideo.cameras.Genicam.QGenicamCamera import QGenicamCamera\n"
            "    raise AssertionError('ImportError not raised')\n"
            "except ImportError as e:\n"
            "    assert 'pip install' in str(e), f'missing install hint: {e}'\n"
        )
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_returns_false_when_no_camera_found(self):
        harvester = MagicMock()
        harvester.create.side_effect = ValueError('no camera')
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                cam = _ConcreteCamera()
        self.assertFalse(cam.isOpen())

    def test_harvester_reset_called_when_no_camera_found(self):
        harvester = MagicMock()
        harvester.create.side_effect = ValueError('no camera')
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                _ConcreteCamera()
        harvester.reset.assert_called_once()

    def test_returns_false_when_producer_fails_to_load(self):
        harvester = MagicMock()
        harvester.add_file.side_effect = OSError('file not found')
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                cam = _ConcreteCamera()
        self.assertFalse(cam.isOpen())

    def test_harvester_reset_called_when_producer_fails_to_load(self):
        harvester = MagicMock()
        harvester.add_file.side_effect = OSError('file not found')
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                _ConcreteCamera()
        harvester.reset.assert_called_once()

    def test_returns_false_when_update_fails(self):
        harvester = MagicMock()
        harvester.update.side_effect = RuntimeError('bad cti')
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                cam = _ConcreteCamera()
        self.assertFalse(cam.isOpen())

    def test_returns_false_when_create_raises_non_value_error(self):
        harvester = MagicMock()
        harvester.create.side_effect = RuntimeError('driver error')
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                cam = _ConcreteCamera()
        self.assertFalse(cam.isOpen())

    def test_returns_false_when_remote_device_is_none(self):
        device = _make_device()
        device.remote_device = None
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                cam = _ConcreteCamera()
        self.assertFalse(cam.isOpen())

    def test_cleanup_called_when_remote_device_is_none(self):
        device = _make_device()
        device.remote_device = None
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                _ConcreteCamera()
        harvester.reset.assert_called_once()

    def test_returns_false_when_node_map_is_none(self):
        device = _make_device()
        device.remote_device.node_map = None
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                cam = _ConcreteCamera()
        self.assertFalse(cam.isOpen())

    def test_cleanup_called_when_node_map_is_none(self):
        device = _make_device()
        device.remote_device.node_map = None
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                _ConcreteCamera()
        harvester.reset.assert_called_once()

    def test_returns_false_when_is_valid_false(self):
        device = _make_device(is_valid=False)
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                cam = _ConcreteCamera()
        self.assertFalse(cam.isOpen())

    def test_cleanup_called_when_is_valid_false(self):
        device = _make_device(is_valid=False)
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                _ConcreteCamera()
        device.stop.assert_called()
        device.destroy.assert_called_once()
        harvester.reset.assert_called_once()

    def test_cleanup_called_when_device_start_raises(self):
        # device.start() raises: exception propagates to caller after cleanup.
        # device was created but never started, so _cleanup still attempts
        # stop() (guarded) then destroy(), then harvester.reset().
        device = _make_device()
        device.start.side_effect = RuntimeError('driver error')
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertRaises(RuntimeError):
                _ConcreteCamera()
        device.destroy.assert_called_once()
        harvester.reset.assert_called_once()

    def test_cleanup_called_when_register_features_raises(self):
        # Exception raised after device.start() has succeeded.
        # _cleanup() must call device.stop() before destroy().
        device = _make_device()
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with patch.object(QGenicamCamera, '_register_features',
                              side_effect=RuntimeError('node error')):
                with self.assertRaises(RuntimeError):
                    _ConcreteCamera()
        device.stop.assert_called()
        device.destroy.assert_called_once()
        harvester.reset.assert_called_once()

    def test_name_returns_class_name(self):
        cam, _, _ = make_camera()
        self.assertEqual(cam.name, '_ConcreteCamera')

    def test_properties_list_populated(self):
        feature = _make_feature(_IInteger, name='Width',
                                min=64, max=1920, inc=4)
        cam, _, _ = make_camera_with_node(feature)
        self.assertIn('Width', cam.properties)

    def test_protected_set_populated(self):
        feature = _make_feature(_IInteger, name='Width')
        feature.node.get_access_mode.side_effect = [
            _EAccessMode.RW,  # _scan_modes before device.start()
            _EAccessMode.RO,  # _scan_modes after  device.start() → protected
            _EAccessMode.RO,  # _register_features (current mode after start)
        ]
        cam, _, _ = make_camera_with_node(feature)
        self.assertIn('Width', cam.protected)


# ---------------------------------------------------------------------------
# TestDeinitialize
# ---------------------------------------------------------------------------

class TestDeinitialize(unittest.TestCase):

    def test_device_stop_called(self):
        cam, _, device = make_camera()
        cam.close()
        device.stop.assert_called()

    def test_device_destroy_called(self):
        cam, _, device = make_camera()
        cam.close()
        device.destroy.assert_called_once()

    def test_harvester_reset_called(self):
        cam, h, _ = make_camera()
        cam.close()
        h.reset.assert_called_once()

    def test_isopen_false_after_close(self):
        cam, _, _ = make_camera()
        cam.close()
        self.assertFalse(cam.isOpen())


# ---------------------------------------------------------------------------
# TestNode
# ---------------------------------------------------------------------------

class TestNode(unittest.TestCase):

    def test_returns_node_when_found(self):
        cam, _, device = make_camera()
        nm = device.remote_device.node_map
        node = cam.node('Width')
        nm.has_node.assert_called_with('Width')
        nm.get_node.assert_called_with('Width')
        self.assertIsNotNone(node)

    def test_returns_none_when_node_map_unset(self):
        harvester = MagicMock()
        harvester.create.side_effect = ValueError('no camera')
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                cam = _ConcreteCamera()
        self.assertIsNone(cam.node('Width'))

    def test_returns_none_when_not_found(self):
        cam, _, device = make_camera()
        device.remote_device.node_map.has_node.return_value = False
        with self.assertLogs('QVideo.cameras.Genicam.QGenicamCamera',
                             level='WARNING'):
            result = cam.node('Nonexistent')
        self.assertIsNone(result)

    def test_default_name_is_root(self):
        cam, _, device = make_camera()
        nm = device.remote_device.node_map
        cam.node()
        nm.has_node.assert_called_with('Root')


# ---------------------------------------------------------------------------
# TestHasNode
# ---------------------------------------------------------------------------

class TestHasNode(unittest.TestCase):

    def test_returns_true_when_node_exists(self):
        cam, _, device = make_camera()
        device.remote_device.node_map.has_node.return_value = True
        self.assertTrue(cam.has_node('Width'))

    def test_returns_false_when_node_not_found(self):
        cam, _, device = make_camera()
        device.remote_device.node_map.has_node.return_value = False
        self.assertFalse(cam.has_node('Nonexistent'))

    def test_returns_false_when_node_map_is_none(self):
        harvester = MagicMock()
        harvester.create.side_effect = ValueError('no camera')
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            with self.assertLogs(level='WARNING'):
                cam = _ConcreteCamera()
        self.assertFalse(cam.has_node('Width'))

    def test_does_not_log_warning_for_unknown_node(self):
        cam, _, device = make_camera()
        device.remote_device.node_map.has_node.return_value = False
        import logging
        with self.assertNoLogs('QVideo.cameras.Genicam.QGenicamCamera',
                               level=logging.WARNING):
            cam.has_node('Nonexistent')


# ---------------------------------------------------------------------------
# TestRead
# ---------------------------------------------------------------------------

class TestRead(unittest.TestCase):

    def test_returns_true_and_array_on_success(self):
        cam, _, _ = make_camera()
        ok, frame = cam.read()
        self.assertTrue(ok)
        self.assertIsInstance(frame, np.ndarray)

    def test_frame_shape(self):
        cam, _, _ = make_camera()
        _, frame = cam.read()
        self.assertEqual(frame.shape, (480, 640))

    def test_returns_false_none_on_timeout(self):
        device = _make_device()
        device.fetch.return_value.__enter__.side_effect = _TimeoutException
        cam, _, _ = make_camera(device=device)
        with self.assertLogs('QVideo.cameras.Genicam.QGenicamCamera',
                             level='WARNING'):
            ok, frame = cam.read()
        self.assertFalse(ok)
        self.assertIsNone(frame)

    def test_returns_false_none_on_general_exception(self):
        device = _make_device()
        device.fetch.return_value.__enter__.side_effect = RuntimeError('driver crash')
        cam, _, _ = make_camera(device=device)
        with self.assertLogs('QVideo.cameras.Genicam.QGenicamCamera',
                             level='WARNING'):
            ok, frame = cam.read()
        self.assertFalse(ok)
        self.assertIsNone(frame)

    def test_returns_false_none_on_empty_payload(self):
        device = _make_device()
        buf = MagicMock()
        buf.payload.components = []
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=buf)
        cm.__exit__ = MagicMock(return_value=False)
        device.fetch.return_value = cm
        cam, _, _ = make_camera(device=device)
        with self.assertLogs('QVideo.cameras.Genicam.QGenicamCamera',
                             level='WARNING'):
            ok, frame = cam.read()
        self.assertFalse(ok)
        self.assertIsNone(frame)


# ---------------------------------------------------------------------------
# TestSet
# ---------------------------------------------------------------------------

class TestSet(unittest.TestCase):

    def test_set_boolean_feature(self):
        feature = _make_feature(_IBoolean, name='ReverseX')
        cam, _, _ = make_camera_with_node(feature)
        cam.set('ReverseX', True)
        self.assertEqual(feature.value, True)

    def test_set_integer_feature(self):
        feature = _make_feature(_IInteger, name='Width',
                                min=64, max=1920, inc=4)
        cam, _, _ = make_camera_with_node(feature)
        cam.set('Width', 640)
        self.assertEqual(feature.value, 640)

    def test_set_float_feature(self):
        feature = _make_feature(_IFloat, name='Gamma', min=0.1, max=4.0)
        feature.has_inc.return_value = False
        cam, _, _ = make_camera_with_node(feature)
        cam.set('Gamma', 1.5)
        self.assertAlmostEqual(feature.value, 1.5)

    def test_set_string_feature(self):
        feature = _make_feature(_IString, name='DeviceUserID')
        cam, _, _ = make_camera_with_node(feature)
        cam.set('DeviceUserID', 'mycam')
        self.assertEqual(feature.value, 'mycam')

    def test_set_enumeration_valid_value(self):
        feature = _make_feature(_IEnumeration, name='PixelFormat')
        entry = MagicMock()
        entry.symbolic = 'Mono8'
        feature.entries = [entry]
        cam, _, _ = make_camera_with_node(feature)
        cam.set('PixelFormat', 'Mono8')
        feature.from_string.assert_called_once_with('Mono8')

    def test_set_enumeration_invalid_value_logs_warning(self):
        feature = _make_feature(_IEnumeration, name='PixelFormat')
        entry = MagicMock()
        entry.symbolic = 'Mono8'
        feature.entries = [entry]
        cam, _, _ = make_camera_with_node(feature)
        with self.assertLogs('QVideo.cameras.Genicam.QGenicamCamera',
                             level='WARNING'):
            cam.set('PixelFormat', 'BadValue')

    def test_set_readonly_feature_does_not_write(self):
        feature = _make_feature(_IInteger, name='Width', mode=_EAccessMode.RO,
                                min=64, max=1920, inc=4)
        cam, _, _ = make_camera_with_node(feature)
        cam.set('Width', 640)
        self.assertNotEqual(feature.value, 640)

    def test_set_stops_and_restarts_protected_feature(self):
        feature = _make_feature(_IInteger, name='Width',
                                min=64, max=1920, inc=4)
        # Mode changes: RW before start → RO after start (protected),
        # then RO during registration.  The setter also checks access mode
        # at runtime (4th call) but proceeds because Width is protected.
        feature.node.get_access_mode.side_effect = [
            _EAccessMode.RW,  # _scan_modes pre-start
            _EAccessMode.RO,  # _scan_modes post-start → protected
            _EAccessMode.RO,  # _register_features
            _EAccessMode.RO,  # setter runtime check
        ]
        device = _make_device()
        root = MagicMock(spec=_ICategory)
        root.features = [feature]
        device.remote_device.node_map.get_node.return_value = root
        cam, _, device = make_camera(device=device)
        device.stop.reset_mock()
        device.start.reset_mock()
        cam.set('Width', 640)
        device.stop.assert_called_once()
        device.start.assert_called_once()

    def test_set_warns_when_feature_becomes_readonly_at_runtime(self):
        feature = _make_feature(_IInteger, name='Gamma', min=0, max=4, inc=1)
        # RW at registration, then RO at runtime (e.g. auto-mode enabled).
        feature.node.get_access_mode.side_effect = [
            _EAccessMode.RW,  # _scan_modes pre-start
            _EAccessMode.RW,  # _scan_modes post-start (not protected)
            _EAccessMode.RW,  # _register_features
            _EAccessMode.RO,  # setter runtime check → should warn and skip
        ]
        cam, _, _ = make_camera_with_node(feature)
        with self.assertLogs('QVideo.cameras.Genicam.QGenicamCamera',
                             level='WARNING'):
            cam.set('Gamma', 2)
        self.assertNotEqual(feature.value, 2)

    def test_set_unknown_key_does_nothing(self):
        cam, _, _ = make_camera()
        with self.assertLogs('QVideo', level='ERROR'):
            cam.set('Nonexistent', 42)


# ---------------------------------------------------------------------------
# TestGet
# ---------------------------------------------------------------------------

class TestGet(unittest.TestCase):

    def test_get_integer_returns_value(self):
        feature = _make_feature(_IInteger, name='Width', value=640)
        cam, _, _ = make_camera_with_node(feature)
        self.assertEqual(cam.get('Width'), 640)

    def test_get_emits_property_value_signal(self):
        feature = _make_feature(_IInteger, name='Width', value=640)
        cam, _, _ = make_camera_with_node(feature)
        spy = QtTest.QSignalSpy(cam.propertyValue)
        cam.get('Width')
        self.assertEqual(len(spy), 1)
        self.assertEqual(spy[0][0], 'Width')

    def test_get_enumeration_returns_string(self):
        feature = _make_feature(_IEnumeration, name='PixelFormat')
        feature.to_string.return_value = 'Mono8'
        cam, _, _ = make_camera_with_node(feature)
        self.assertEqual(cam.get('PixelFormat'), 'Mono8')

    def test_get_ni_feature_not_registered(self):
        feature = _make_feature(_IInteger, name='Width', mode=_EAccessMode.NI)
        cam, _, _ = make_camera_with_node(feature)
        self.assertNotIn('Width', cam.properties)

    def test_get_unknown_key_returns_none(self):
        cam, _, _ = make_camera()
        with self.assertLogs('QVideo', level='ERROR'):
            result = cam.get('Nonexistent')
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# TestExecute
# ---------------------------------------------------------------------------

class TestExecute(unittest.TestCase):

    def test_executes_command_node(self):
        feature = _make_feature(_ICommand, name='AcquisitionStop')
        cam, _, _ = make_camera_with_node(feature)
        cam.execute('AcquisitionStop')
        feature.execute.assert_called_once()

    def test_non_command_node_not_executed(self):
        feature = _make_feature(_IInteger, name='Width',
                                min=64, max=1920, inc=4)
        cam, _, _ = make_camera_with_node(feature)
        with self.assertLogs('QVideo', level='ERROR'):
            cam.execute('Width')
        feature.execute.assert_not_called()


# ---------------------------------------------------------------------------
# TestIsReadwrite
# ---------------------------------------------------------------------------

class TestIsReadwrite(unittest.TestCase):

    def test_rw_mode_returns_true(self):
        cam, _, device = make_camera()
        feature = _make_feature(_IInteger, name='Width',
                                mode=_EAccessMode.RW)
        device.remote_device.node_map.get_node.return_value = feature
        self.assertTrue(cam.is_readwrite('Width'))

    def test_ro_mode_returns_false(self):
        cam, _, device = make_camera()
        cam.protected = set()
        feature = _make_feature(_IInteger, name='Width',
                                mode=_EAccessMode.RO)
        device.remote_device.node_map.get_node.return_value = feature
        self.assertFalse(cam.is_readwrite('Width'))

    def test_protected_feature_returns_true(self):
        cam, _, device = make_camera()
        cam.protected = {'Width'}
        feature = _make_feature(_IInteger, name='Width',
                                mode=_EAccessMode.RO)
        device.remote_device.node_map.get_node.return_value = feature
        self.assertTrue(cam.is_readwrite('Width'))

    def test_unknown_node_returns_false(self):
        cam, _, device = make_camera()
        device.remote_device.node_map.has_node.return_value = False
        with self.assertLogs('QVideo.cameras.Genicam.QGenicamCamera',
                             level='WARNING'):
            result = cam.is_readwrite('Nonexistent')
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# TestWidthHeight
# ---------------------------------------------------------------------------

class TestWidthHeight(unittest.TestCase):

    def _make_dim_feature(self, name, value):
        return _make_feature(_IInteger, name=name,
                             value=value, min=64, max=4096, inc=4)

    def test_width_getter(self):
        feature = self._make_dim_feature('Width', 640)
        cam, _, _ = make_camera_with_node(feature)
        self.assertEqual(cam.width, 640)

    def test_height_getter(self):
        feature = self._make_dim_feature('Height', 480)
        cam, _, _ = make_camera_with_node(feature)
        self.assertEqual(cam.height, 480)

    def test_width_setter_emits_shape_changed(self):
        feature = self._make_dim_feature('Width', 640)
        cam, _, _ = make_camera_with_node(feature)
        spy = QtTest.QSignalSpy(cam.shapeChanged)
        cam.set('Width', 640)
        self.assertEqual(len(spy), 1)

    def test_height_setter_emits_shape_changed(self):
        feature = self._make_dim_feature('Height', 480)
        cam, _, _ = make_camera_with_node(feature)
        spy = QtTest.QSignalSpy(cam.shapeChanged)
        cam.set('Height', 480)
        self.assertEqual(len(spy), 1)


# ---------------------------------------------------------------------------
# TestQGenicamSource
# ---------------------------------------------------------------------------

class TestQGenicamSource(unittest.TestCase):

    def test_uses_provided_camera(self):
        cam, _, _ = make_camera()
        src = QGenicamSource(camera=cam)
        self.assertIs(src.source, cam)


if __name__ == '__main__':
    unittest.main()
