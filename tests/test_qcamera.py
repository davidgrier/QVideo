'''Unit tests for QCamera.'''
import unittest
import numpy as np
from unittest.mock import patch
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
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

    def _initialize(self, *args, **kwargs) -> bool:
        self._initialize_called += 1
        return True

    def _deinitialize(self) -> None:
        self._deinitialize_called += 1

    def read(self) -> QCamera.CameraData:
        frame = np.zeros((self._height, self._width), dtype=np.uint8)
        return True, frame

    @QtCore.pyqtProperty(bool)
    def color(self) -> bool:
        return False

    @QtCore.pyqtProperty(int)
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        self._width = value
        self.shapeChanged.emit(self.shape)

    @QtCore.pyqtProperty(int)
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        self._height = value
        self.shapeChanged.emit(self.shape)

    @QtCore.pyqtProperty(float)
    def fps(self) -> float:
        return self._fps

    @fps.setter
    def fps(self, value: float) -> None:
        self._fps = value


def make_camera() -> _FakeCamera:
    return _FakeCamera()


class TestInit(unittest.TestCase):

    def test_name_is_class_name(self):
        cam = make_camera()
        self.assertEqual(cam.name, '_FakeCamera')

    def test_initially_closed(self):
        cam = make_camera()
        self.assertFalse(cam.isOpen())

    def test_initially_not_paused(self):
        cam = make_camera()
        self.assertFalse(cam.isPaused())

    def test_has_mutex(self):
        cam = make_camera()
        self.assertIsInstance(cam.mutex, QtCore.QMutex)

    def test_has_waitcondition(self):
        cam = make_camera()
        self.assertIsInstance(cam.waitcondition, QtCore.QWaitCondition)


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


class TestProperties(unittest.TestCase):

    def test_properties_returns_list(self):
        cam = make_camera()
        self.assertIsInstance(cam.properties(), list)

    def test_known_properties_present(self):
        cam = make_camera()
        for name in ('width', 'height', 'fps', 'color'):
            self.assertIn(name, cam.properties())

    def test_methods_returns_list(self):
        cam = make_camera()
        self.assertIsInstance(cam.methods(), list)


class TestShape(unittest.TestCase):

    def test_shape_returns_qsize(self):
        cam = make_camera()
        self.assertIsInstance(cam.shape, QtCore.QSize)

    def test_shape_matches_width_height(self):
        cam = make_camera()
        self.assertEqual(cam.shape, QtCore.QSize(cam.width, cam.height))

    def test_shape_updates_with_width(self):
        cam = make_camera()
        cam.width = 320
        self.assertEqual(cam.shape.width(), 320)

    def test_shape_updates_with_height(self):
        cam = make_camera()
        cam.height = 240
        self.assertEqual(cam.shape.height(), 240)

    def test_shape_changed_emitted_on_width_change(self):
        cam = make_camera()
        spy = QtTest.QSignalSpy(cam.shapeChanged)
        cam.width = 320
        self.assertEqual(len(spy), 1)

    def test_shape_changed_emitted_on_height_change(self):
        cam = make_camera()
        spy = QtTest.QSignalSpy(cam.shapeChanged)
        cam.height = 240
        self.assertEqual(len(spy), 1)


class TestSettings(unittest.TestCase):

    def test_settings_returns_dict(self):
        cam = make_camera()
        self.assertIsInstance(cam.settings(), dict)

    def test_settings_contains_known_properties(self):
        cam = make_camera()
        s = cam.settings()
        self.assertIn('width', s)
        self.assertIn('height', s)
        self.assertIn('fps', s)

    def test_set_valid_property(self):
        cam = make_camera()
        cam.set('width', 320)
        self.assertEqual(cam.width, 320)

    def test_set_invalid_property_logs_error(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='ERROR'):
            cam.set('nonexistent', 42)

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
        spy = QtTest.QSignalSpy(cam.propertyValue)
        cam.get('width')
        self.assertEqual(len(spy), 1)
        name, value = spy[0]
        self.assertEqual(name, 'width')
        self.assertEqual(value, 640)

    def test_set_settings_applies_all(self):
        cam = make_camera()
        cam.setSettings({'width': 320, 'height': 240})
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


class TestPauseResume(unittest.TestCase):

    def test_pause_sets_paused(self):
        cam = make_camera()
        cam.pause()
        self.assertTrue(cam.isPaused())

    def test_resume_wakes_condition(self):
        cam = make_camera()
        with patch.object(cam.waitcondition, 'wakeAll') as mock_wake:
            cam.resume()
            self.assertTrue(mock_wake.called)


class TestExecute(unittest.TestCase):

    def test_execute_invalid_method_logs_error(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='ERROR'):
            cam.execute('nonexistent')


if __name__ == '__main__':
    unittest.main()
