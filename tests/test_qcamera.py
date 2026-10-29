'''Unit tests for QCamera.'''
import threading
import time
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.tests.signals import record
from QVideo.lib.QCamera import QCamera


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _FakeCamera(QCamera):
    '''Minimal concrete QCamera for testing.'''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._width = 640
        self._height = 480
        self._fps = 30.
        self._initialize_called = 0
        self._deinitialize_called = 0
        self._method_called = False

        def _set_width(v):
            self._width = int(v)
            self.shapeChanged.emit(self.shape)

        def _set_height(v):
            self._height = int(v)
            self.shapeChanged.emit(self.shape)

        self.registerProperty('width', setter=_set_width, ptype=int)
        self.registerProperty('height', setter=_set_height, ptype=int)
        self.registerProperty('fps', ptype=float)
        self.registerProperty('color', getter=lambda: False, setter=None, ptype=bool)
        self.registerMethod('calibrate', self.calibrate)

    def _initialize(self, *args, **kwargs) -> bool:
        self._initialize_called += 1
        return True

    def _deinitialize(self) -> None:
        self._deinitialize_called += 1

    def read(self) -> QCamera.CameraData:
        frame = np.zeros((self._height, self._width), dtype=np.uint8)
        return True, frame

    def calibrate(self) -> None:
        self._method_called = True


def make_camera() -> _FakeCamera:
    return _FakeCamera()


class TestInit(unittest.TestCase):

    def test_name_is_class_name(self):
        cam = make_camera()
        self.assertEqual(cam.name, '_FakeCamera')

    def test_model_name_default_none(self):
        cam = make_camera()
        self.assertIsNone(cam.model_name)

    def test_model_name_reflects_model_name(self):
        cam = make_camera()
        cam._modelName = 'MyCamera'
        self.assertEqual(cam.model_name, 'MyCamera')

    def test_initially_closed(self):
        cam = make_camera()
        self.assertFalse(cam.isOpen())

    def test_has_mutex(self):
        cam = make_camera()
        self.assertIsInstance(cam._mutex, type(threading.RLock()))



class TestOpen(unittest.TestCase):

    def test_open_returns_self(self):
        cam = make_camera()
        self.assertIs(cam.open(), cam)

    def test_open_sets_isopen(self):
        cam = make_camera()
        cam.open()
        self.assertTrue(cam.isOpen())

    def test_open_calls_initialize(self):
        cam = make_camera()
        cam.open()
        self.assertEqual(cam._initialize_called, 1)

    def test_open_is_idempotent(self):
        cam = make_camera()
        cam.open()
        cam.open()
        self.assertEqual(cam._initialize_called, 1)

    def test_open_returns_self_on_failure(self):
        cam = make_camera()
        with patch.object(cam, '_initialize', return_value=False):
            with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
                result = cam.open()
        self.assertIs(result, cam)

    def test_open_logs_warning_on_failure(self):
        cam = make_camera()
        with patch.object(cam, '_initialize', return_value=False):
            with self.assertLogs('QVideo.lib.QCamera', level='WARNING') as cm:
                cam.open()
        self.assertTrue(any('initialization failed' in line for line in cm.output))

    def test_open_leaves_closed_on_failure(self):
        cam = make_camera()
        with patch.object(cam, '_initialize', return_value=False):
            with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
                cam.open()
        self.assertFalse(cam.isOpen())


class TestClose(unittest.TestCase):

    def test_close_clears_isopen(self):
        cam = make_camera()
        cam.open()
        cam.close()
        self.assertFalse(cam.isOpen())

    def test_close_calls_deinitialize(self):
        cam = make_camera()
        cam.open()
        cam.close()
        self.assertEqual(cam._deinitialize_called, 1)

    def test_close_is_idempotent(self):
        cam = make_camera()
        cam.open()
        cam.close()
        cam.close()
        self.assertEqual(cam._deinitialize_called, 1)

    def test_close_when_never_opened(self):
        cam = make_camera()
        try:
            cam.close()
        except Exception as e:
            self.fail(f'close() on unopened camera raised {e}')


class TestContextManager(unittest.TestCase):

    def test_enter_opens_camera(self):
        cam = make_camera()
        with cam:
            self.assertTrue(cam.isOpen())

    def test_exit_closes_camera(self):
        cam = make_camera()
        with cam:
            pass
        self.assertFalse(cam.isOpen())

    def test_can_reopen_after_context(self):
        cam = make_camera()
        with cam:
            pass
        with cam:
            self.assertTrue(cam.isOpen())


class TestRegistration(unittest.TestCase):

    def test_properties_returns_list(self):
        cam = make_camera()
        self.assertIsInstance(cam.properties, dict)

    def test_registered_properties_present(self):
        cam = make_camera()
        for name in ('width', 'height', 'fps', 'color'):
            self.assertIn(name, cam.properties)

    def test_methods_returns_list(self):
        cam = make_camera()
        self.assertIsInstance(cam.methods, list)

    def test_registered_method_present(self):
        cam = make_camera()
        self.assertIn('calibrate', cam.methods)

    def test_auto_getter_reads_backing_attribute(self):
        cam = make_camera()
        cam._fps = 60.
        self.assertEqual(cam.get('fps'), 60.)

    def test_auto_setter_writes_backing_attribute(self):
        cam = make_camera()
        cam.set('fps', 24.)
        self.assertAlmostEqual(cam._fps, 24.)

    def test_auto_setter_coerces_to_ptype(self):
        cam = make_camera()
        cam.set('width', 320.9)   # float passed, ptype=int
        self.assertIsInstance(cam._width, int)
        self.assertEqual(cam._width, 320)

    def test_explicit_setter_none_is_read_only(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
            cam.set('color', True)
        self.assertFalse(cam.color)

    def test_subclass_inherits_and_extends_registrations(self):
        class _ExtendedCamera(_FakeCamera):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._gain = 0
                self.registerProperty('gain',
                                      getter=lambda: self._gain,
                                      setter=lambda v: setattr(self, '_gain', int(v)),
                                      ptype=int)
        cam = _ExtendedCamera()
        self.assertIn('gain', cam.properties)
        self.assertIn('width', cam.properties)


class TestGetattr(unittest.TestCase):

    def test_registered_property_accessible_as_attribute(self):
        cam = make_camera()
        self.assertEqual(cam.width, 640)

    def test_registered_property_attribute_updates_with_setter(self):
        cam = make_camera()
        cam.set('width', 320)
        self.assertEqual(cam.width, 320)

    def test_unregistered_attribute_raises(self):
        cam = make_camera()
        with self.assertRaises(AttributeError):
            _ = cam.nonexistent


class TestSetattr(unittest.TestCase):

    def test_attribute_assignment_calls_setter(self):
        cam = make_camera()
        cam.fps = 60.
        self.assertAlmostEqual(cam.fps, 60.)

    def test_attribute_assignment_routes_through_registered_setter(self):
        cam = make_camera()
        cam.width = 320
        self.assertEqual(cam.width, 320)

    def test_attribute_assignment_coerces_to_ptype(self):
        cam = make_camera()
        cam.width = '1280'
        self.assertEqual(cam.width, 1280)
        self.assertIsInstance(cam.width, int)

    def test_attribute_assignment_to_readonly_logs_warning(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
            cam.color = True

    def test_unregistered_attribute_assignment_sets_python_attribute(self):
        cam = make_camera()
        cam.custom_attr = 'hello'
        self.assertEqual(cam.custom_attr, 'hello')

    def test_internal_attribute_set_directly(self):
        cam = make_camera()
        cam._fps = 99.
        self.assertAlmostEqual(cam._fps, 99.)

    def test_custom_setter_called_on_attribute_assignment(self):
        setter_calls = []
        cam = make_camera()
        cam.registerProperty('gain', getter=lambda: 1.0,
                             setter=lambda v: setter_calls.append(v), ptype=float)
        cam.gain = 2.5
        self.assertEqual(setter_calls, [2.5])


class TestActualFps(unittest.TestCase):

    def test_it_is_the_requested_rate_by_default(self):
        self.assertEqual(make_camera().actualFps, 30.)

    def test_it_follows_the_requested_rate(self):
        camera = make_camera()
        camera.fps = 12.
        self.assertEqual(camera.actualFps, 12.)

    def test_it_is_read_only(self):
        with self.assertRaises(AttributeError):
            make_camera().actualFps = 10.

    def test_a_subclass_can_report_what_the_hardware_does(self):
        class Slow(_FakeCamera):
            @property
            def actualFps(self):
                return 0.5 * self.fps
        camera = Slow()
        camera.fps = 20.
        self.assertEqual((camera.fps, camera.actualFps), (20., 10.))


class TestShape(unittest.TestCase):

    def test_shape_returns_qsize(self):
        cam = make_camera()
        self.assertIsInstance(cam.shape, QtCore.QSize)

    def test_shape_matches_registered_width_height(self):
        cam = make_camera()
        self.assertEqual(cam.shape, QtCore.QSize(640, 480))

    def test_shape_updates_with_width(self):
        cam = make_camera()
        cam.set('width', 320)
        self.assertEqual(cam.shape.width(), 320)

    def test_shape_updates_with_height(self):
        cam = make_camera()
        cam.set('height', 240)
        self.assertEqual(cam.shape.height(), 240)

    def test_shape_changed_emitted_on_width_change(self):
        cam = make_camera()
        spy = record(cam.shapeChanged)
        cam.set('width', 320)
        self.assertEqual(len(spy), 1)

    def test_shape_changed_emitted_on_height_change(self):
        cam = make_camera()
        spy = record(cam.shapeChanged)
        cam.set('height', 240)
        self.assertEqual(len(spy), 1)

    def test_shape_returns_zero_size_when_not_registered(self):
        cam = make_camera()
        cam.properties.clear()
        self.assertEqual(cam.shape, QtCore.QSize(0, 0))


class _StandardCamera(_FakeCamera):
    '''A camera whose properties have the names of a standard.'''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.properties.clear()
        self._Width, self._Height, self._Rate = 640, 480, 30.
        self.registerProperty('Width', ptype=int)
        self.registerProperty('Height', ptype=int)
        self.registerProperty('Rate', ptype=float)
        self.aliases.update(width='Width', height='Height', fps='Rate')


class TestAliases(unittest.TestCase):
    '''Other names for properties, for the names that every camera shares.'''

    def setUp(self):
        self.cam = _StandardCamera()

    def test_there_are_none_by_default(self):
        self.assertEqual(make_camera().aliases, {})

    def test_an_alias_is_not_a_property(self):
        self.assertNotIn('width', self.cam.properties)
        self.assertIn('Width', self.cam.properties)

    def test_the_settings_and_the_properties_have_the_same_names(self):
        self.assertEqual(set(self.cam.settings), set(self.cam.properties))

    def test_an_alias_reads_as_an_attribute(self):
        self.assertEqual(self.cam.width, 640)
        self.assertEqual(self.cam.fps, 30.)

    def test_an_alias_writes_as_an_attribute(self):
        self.cam.width = 320
        self.assertEqual(self.cam._Width, 320)
        self.assertNotIn('width', self.cam.__dict__)

    def test_get_takes_an_alias(self):
        self.assertEqual(self.cam.get('height'), 480)

    def test_get_emits_the_name_of_the_property(self):
        spy = record(self.cam.propertyValue)
        self.cam.get('height')
        self.assertEqual(spy, [('Height', 480)])

    def test_set_takes_an_alias(self):
        self.cam.set('fps', 15.)
        self.assertEqual(self.cam._Rate, 15.)

    def test_the_shape_is_found_by_alias(self):
        self.assertEqual(self.cam.shape, QtCore.QSize(640, 480))

    def test_an_unknown_name_is_still_an_error_that_names_it(self):
        with self.assertRaisesRegex(AttributeError, 'nonsense'):
            self.cam.nonsense


class TestSettings(unittest.TestCase):

    def test_settings_returns_dict(self):
        cam = make_camera()
        self.assertIsInstance(cam.settings, dict)

    def test_settings_contains_registered_properties(self):
        cam = make_camera()
        s = cam.settings
        self.assertIn('width', s)
        self.assertIn('height', s)
        self.assertIn('fps', s)

    def test_settings_does_not_emit_property_value_signal(self):
        cam = make_camera()
        spy = record(cam.propertyValue)
        cam.settings
        self.assertEqual(len(spy), 0)

    def test_set_valid_property(self):
        cam = make_camera()
        cam.set('width', 320)
        self.assertEqual(cam.width, 320)

    def test_set_invalid_property_logs_error(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='ERROR'):
            cam.set('nonexistent', 42)

    def test_set_read_only_property_logs_warning(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
            cam.set('color', True)

    def test_get_valid_property(self):
        cam = make_camera()
        self.assertEqual(cam.get('width'), 640)

    def test_get_invalid_property_returns_none(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='ERROR'):
            result = cam.get('nonexistent')
        self.assertIsNone(result)

    def test_get_emits_property_value_signal(self):
        cam = make_camera()
        spy = record(cam.propertyValue)
        cam.get('width')
        self.assertEqual(len(spy), 1)
        name, value = spy[0]
        self.assertEqual(name, 'width')
        self.assertEqual(value, 640)

    def test_set_settings_applies_all(self):
        cam = make_camera()
        cam.settings = {'width': 320, 'height': 240}
        self.assertEqual(cam.width, 320)
        self.assertEqual(cam.height, 240)


class TestRead(unittest.TestCase):

    def test_read_returns_tuple(self):
        cam = make_camera()
        result = cam.read()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_read_success_flag(self):
        cam = make_camera()
        success, _ = cam.read()
        self.assertTrue(success)

    def test_read_returns_ndarray(self):
        cam = make_camera()
        _, frame = cam.read()
        self.assertIsInstance(frame, np.ndarray)

    def test_read_frame_shape(self):
        cam = make_camera()
        _, frame = cam.read()
        self.assertEqual(frame.shape, (480, 640))

    def test_saferead_calls_read(self):
        cam = make_camera()
        with patch.object(cam, 'read', wraps=cam.read) as mock_read:
            cam.saferead()
            self.assertTrue(mock_read.called)


class TestExecute(unittest.TestCase):

    def test_execute_calls_method(self):
        cam = make_camera()
        cam.execute('calibrate')
        self.assertTrue(cam._method_called)

    def test_execute_invalid_method_logs_error(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='ERROR'):
            cam.execute('nonexistent')


class TestSerialization(unittest.TestCase):
    '''No device access overlaps a frame read, by any route.'''

    def setUp(self):
        self.cam = make_camera()
        self.reading = threading.Event()
        self.overlaps = []

        def slow_read():
            self.reading.set()
            time.sleep(0.15)
            self.reading.clear()
            return True, np.zeros((4, 4), dtype=np.uint8)

        def checked(value):
            def getter():
                self.overlaps.append(self.reading.is_set())
                return value
            return getter

        self.cam.read = slow_read
        self.cam.registerProperty('probe', getter=checked(1), ptype=int)
        self.cam.registerMethod('act', checked(None))

    def during_a_read(self, access):
        thread = threading.Thread(target=self.cam.saferead)
        thread.start()
        self.reading.wait(1)
        access()
        thread.join()
        self.assertEqual(self.overlaps, [False])

    def test_attribute_access(self):
        self.during_a_read(lambda: self.cam.probe)

    def test_get(self):
        self.during_a_read(lambda: self.cam.get('probe'))

    def test_settings(self):
        self.during_a_read(lambda: self.cam.settings)

    def test_execute(self):
        self.during_a_read(lambda: self.cam.execute('act'))

    def test_set(self):
        self.cam.registerProperty('probe', getter=lambda: 1, ptype=int,
                                  setter=lambda v: self.overlaps.append(
                                      self.reading.is_set()))
        self.during_a_read(lambda: self.cam.set('probe', 2))

    def test_a_setter_may_read_other_properties(self):
        self.cam.set('width', 320)
        self.assertEqual(self.cam.shape.width(), 320)


if __name__ == '__main__':
    unittest.main()
