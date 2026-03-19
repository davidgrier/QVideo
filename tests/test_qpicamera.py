'''Unit tests for QPicamera and QPicameraSource.'''
import sys
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from pyqtgraph.Qt import QtWidgets, QtTest

from QVideo.cameras.Picamera._camera import QPicamera, QPicameraSource

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_MODULE = sys.modules['QVideo.cameras.Picamera._camera']

_FRAME_RGB = np.zeros((960, 1280, 3), dtype=np.uint8)

_CAMERA_CONTROLS = {
    'AeEnable':          (False, True,      True),
    'AwbEnable':         (False, True,      True),
    'Brightness':        (-1.0,  1.0,       0.0),
    'Contrast':          (0.0,   32.0,      1.0),
    'Saturation':        (0.0,   32.0,      1.0),
    'Sharpness':         (0.0,   16.0,      1.0),
    'ExposureTime':      (100,   1000000,   10000),
    'AnalogueGain':      (1.0,   16.0,      1.0),
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

def make_mock_device(width=1280, height=960, frame=None,
                     capture_ok=True, controls=None, metadata=None):
    '''Return a MagicMock standing in for a Picamera2 instance.'''
    if frame is None:
        frame = _FRAME_RGB.copy()
    if controls is None:
        controls = _CAMERA_CONTROLS.copy()
    if metadata is None:
        metadata = _METADATA.copy()
    device = MagicMock()
    device.camera_controls = controls
    device.camera_config = {'main': {'size': (width, height),
                                     'format': 'RGB888'}}
    if capture_ok:
        device.capture_array.return_value = frame.copy()
        request = MagicMock()
        request.make_array.return_value = frame.copy()
        device.capture_request.return_value = request
    else:
        device.capture_array.side_effect = RuntimeError('no frame')
        device.capture_request.side_effect = RuntimeError('no frame')
    device.capture_metadata.return_value = metadata.copy()
    return device


def make_camera(cameraID=0, width=1280, height=960,
                capture_ok=True, controls=None, metadata=None):
    '''Return a QPicamera with a mocked Picamera2 device.'''
    device = make_mock_device(width=width, height=height,
                              capture_ok=capture_ok,
                              controls=controls, metadata=metadata)
    with patch.object(_MODULE, 'Picamera2', return_value=device):
        cam = QPicamera(cameraID=cameraID, width=width, height=height)
    return cam, device


class TestAll(unittest.TestCase):

    def test_all_defined(self):
        self.assertTrue(hasattr(_MODULE, '__all__'))

    def test_all_contains_qpicamera(self):
        self.assertIn('QPicamera', _MODULE.__all__)

    def test_all_contains_qpicamerasource(self):
        self.assertIn('QPicameraSource', _MODULE.__all__)


class TestInit(unittest.TestCase):

    def test_opens_on_init(self):
        cam, _ = make_camera()
        self.assertTrue(cam.isOpen())
        cam.close()

    def test_default_camera_id(self):
        cam, _ = make_camera()
        self.assertEqual(cam.cameraID, 0)
        cam.close()

    def test_custom_camera_id(self):
        cam, _ = make_camera(cameraID=1)
        self.assertEqual(cam.cameraID, 1)
        cam.close()

    def test_picamera2_called_with_camera_num(self):
        device = make_mock_device()
        with patch.object(_MODULE, 'Picamera2', return_value=device) as mock_cls:
            cam = QPicamera(cameraID=2)
        mock_cls.assert_called_once_with(camera_num=2)
        cam.close()

    def test_default_width(self):
        cam, _ = make_camera()
        self.assertEqual(cam.width, 1280)
        cam.close()

    def test_default_height(self):
        cam, _ = make_camera()
        self.assertEqual(cam.height, 960)
        cam.close()

    def test_configure_called_with_rgb888(self):
        cam, device = make_camera()
        config_args = device.create_preview_configuration.call_args
        main = config_args.kwargs.get('main', config_args[1].get('main'))
        self.assertEqual(main['format'], 'RGB888')
        cam.close()


class TestInitializationFailure(unittest.TestCase):

    def test_picamera2_none_returns_closed(self):
        with patch.object(_MODULE, 'Picamera2', None):
            cam = QPicamera()
        self.assertFalse(cam.isOpen())

    def test_picamera2_constructor_error_returns_closed(self):
        with patch.object(_MODULE, 'Picamera2', side_effect=RuntimeError('no cam')):
            cam = QPicamera()
        self.assertFalse(cam.isOpen())

    def test_no_frame_returns_closed(self):
        cam, _ = make_camera(capture_ok=False)
        self.assertFalse(cam.isOpen())


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.cam, self.device = make_camera()

    def tearDown(self):
        self.cam.close()

    def test_width_registered(self):
        self.assertIn('width', self.cam.properties)

    def test_height_registered(self):
        self.assertIn('height', self.cam.properties)

    def test_color_registered(self):
        self.assertIn('color', self.cam.properties)

    def test_color_is_true(self):
        self.assertTrue(self.cam.color)

    def test_color_is_readonly(self):
        self.assertIsNone(self.cam._properties['color']['setter'])

    def test_brightness_registered(self):
        self.assertIn('Brightness', self.cam.properties)

    def test_contrast_registered(self):
        self.assertIn('Contrast', self.cam.properties)

    def test_saturation_registered(self):
        self.assertIn('Saturation', self.cam.properties)

    def test_sharpness_registered(self):
        self.assertIn('Sharpness', self.cam.properties)

    def test_exposure_registered(self):
        self.assertIn('ExposureTime', self.cam.properties)

    def test_analogue_gain_registered(self):
        self.assertIn('AnalogueGain', self.cam.properties)

    def test_ae_enable_registered(self):
        self.assertIn('AeEnable', self.cam.properties)

    def test_awb_enable_registered(self):
        self.assertIn('AwbEnable', self.cam.properties)

    def test_brightness_initial_value(self):
        self.assertEqual(self.cam.Brightness, 0.0)

    def test_exposure_initial_value(self):
        self.assertEqual(self.cam.ExposureTime, 10000)

    def test_ae_enable_initial_value(self):
        self.assertIsInstance(self.cam.AeEnable, bool)
        self.assertTrue(self.cam.AeEnable)

    def test_float_control_has_minimum(self):
        spec = self.cam._properties['Brightness']
        self.assertIn('minimum', spec)

    def test_float_control_has_maximum(self):
        spec = self.cam._properties['Brightness']
        self.assertIn('maximum', spec)

    def test_float_control_minimum_value(self):
        self.assertEqual(self.cam._properties['Brightness']['minimum'], -1.0)

    def test_float_control_maximum_value(self):
        self.assertEqual(self.cam._properties['Brightness']['maximum'], 1.0)

    def test_bool_control_has_no_minimum(self):
        spec = self.cam._properties['AeEnable']
        self.assertNotIn('minimum', spec)

    def test_bool_control_has_no_maximum(self):
        spec = self.cam._properties['AeEnable']
        self.assertNotIn('maximum', spec)

    def test_unknown_control_not_registered(self):
        self.assertNotIn('NoSuchControl', self.cam.properties)

    def test_missing_control_skipped(self):
        controls = {k: v for k, v in _CAMERA_CONTROLS.items()
                    if k != 'Sharpness'}
        cam, _ = make_camera(controls=controls)
        self.assertNotIn('Sharpness', cam.properties)
        cam.close()


class TestSetControl(unittest.TestCase):

    def setUp(self):
        self.cam, self.device = make_camera()

    def tearDown(self):
        self.cam.close()

    def test_set_control_calls_set_controls(self):
        self.cam.set('Brightness', 0.5)
        self.device.set_controls.assert_called_with({'Brightness': 0.5})

    def test_set_control_updates_cache(self):
        self.cam.set('Brightness', 0.5)
        self.assertEqual(self.cam.Brightness, 0.5)

    def test_set_exposure_value(self):
        self.cam.set('ExposureTime', 20000)
        self.device.set_controls.assert_called_with({'ExposureTime': 20000})


class TestReconfigure(unittest.TestCase):

    def setUp(self):
        self.cam, self.device = make_camera()

    def tearDown(self):
        self.cam.close()

    def test_set_width_calls_stop_and_start(self):
        self.device.reset_mock()
        self.cam.set('width', 640)
        self.device.stop.assert_called()
        self.device.start.assert_called()

    def test_set_height_calls_stop_and_start(self):
        self.device.reset_mock()
        self.cam.set('height', 480)
        self.device.stop.assert_called()
        self.device.start.assert_called()

    def test_set_width_emits_shape_changed(self):
        spy = QtTest.QSignalSpy(self.cam.shapeChanged)
        self.cam.set('width', 640)
        self.assertGreater(len(spy), 0)

    def test_set_height_emits_shape_changed(self):
        spy = QtTest.QSignalSpy(self.cam.shapeChanged)
        self.cam.set('height', 480)
        self.assertGreater(len(spy), 0)

    def test_reconfigure_reapplies_controls(self):
        self.cam.set('Brightness', 0.3)
        self.device.reset_mock()
        self.cam.set('width', 640)
        self.device.set_controls.assert_called()

    def test_reconfigure_uses_rgb888_format(self):
        self.device.reset_mock()
        self.cam.set('width', 640)
        config_args = self.device.create_preview_configuration.call_args
        main = config_args.kwargs.get('main', config_args[1].get('main'))
        self.assertEqual(main['format'], 'RGB888')


class TestRead(unittest.TestCase):

    def setUp(self):
        self.cam, self.device = make_camera()

    def tearDown(self):
        self.cam.close()

    def test_read_returns_true_on_success(self):
        ok, _ = self.cam.read()
        self.assertTrue(ok)

    def test_read_returns_rgb_frame(self):
        _, frame = self.cam.read()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.ndim, 3)
        self.assertEqual(frame.shape[2], 3)

    def test_read_uses_capture_request(self):
        self.cam.read()
        self.device.capture_request.assert_called()

    def test_read_calls_make_array_on_request(self):
        self.cam.read()
        request = self.device.capture_request.return_value
        request.make_array.assert_called_with('main')

    def test_read_releases_request(self):
        self.cam.read()
        request = self.device.capture_request.return_value
        request.release.assert_called()

    def test_read_returns_false_when_closed(self):
        self.cam.close()
        ok, frame = self.cam.read()
        self.assertFalse(ok)
        self.assertIsNone(frame)

    def test_read_returns_false_on_capture_error(self):
        self.device.capture_request.side_effect = RuntimeError('error')
        ok, frame = self.cam.read()
        self.assertFalse(ok)
        self.assertIsNone(frame)


class TestFrameRate(unittest.TestCase):

    def setUp(self):
        self.cam, self.device = make_camera()

    def tearDown(self):
        self.cam.close()

    def test_fps_registered(self):
        self.assertIn('fps', self.cam.properties)

    def test_fps_initial_value(self):
        self.assertAlmostEqual(self.cam.fps, 1_000_000 / 33333, places=1)

    def test_fps_maximum(self):
        spec = self.cam._properties['fps']
        self.assertAlmostEqual(spec['maximum'], 1_000_000 / 33333, places=1)

    def test_fps_minimum(self):
        spec = self.cam._properties['fps']
        self.assertAlmostEqual(spec['minimum'], 1_000_000 / 120000000, places=4)

    def test_set_fps_calls_set_controls(self):
        self.cam.set('fps', 15.0)
        duration = int(1_000_000 / 15.0)
        self.device.set_controls.assert_called_with(
            {'FrameDurationLimits': (duration, duration)})

    def test_set_fps_updates_cached_value(self):
        self.cam.set('fps', 15.0)
        self.assertAlmostEqual(self.cam.fps, 15.0, places=1)

    def test_fps_not_registered_without_control(self):
        controls = {k: v for k, v in _CAMERA_CONTROLS.items()
                    if k != 'FrameDurationLimits'}
        cam, _ = make_camera(controls=controls)
        self.assertNotIn('fps', cam.properties)
        cam.close()

    def test_fps_reapplied_after_reconfigure(self):
        self.cam.set('fps', 15.0)
        self.device.reset_mock()
        self.cam.set('width', 640)
        self.device.set_controls.assert_called()


class TestDeinitialize(unittest.TestCase):

    def test_close_calls_stop(self):
        cam, device = make_camera()
        cam.close()
        device.stop.assert_called()

    def test_close_calls_device_close(self):
        cam, device = make_camera()
        cam.close()
        device.close.assert_called()

    def test_camera_not_open_after_close(self):
        cam, _ = make_camera()
        cam.close()
        self.assertFalse(cam.isOpen())


class TestQPicameraSource(unittest.TestCase):

    def test_source_wraps_new_camera(self):
        device = make_mock_device()
        with patch.object(_MODULE, 'Picamera2', return_value=device):
            src = QPicameraSource()
        self.assertTrue(src.source.isOpen())
        src.source.close()

    def test_source_accepts_existing_camera(self):
        cam, _ = make_camera()
        src = QPicameraSource(camera=cam)
        self.assertIs(src.source, cam)
        cam.close()

    def test_source_forwards_camera_id(self):
        device = make_mock_device()
        with patch.object(_MODULE, 'Picamera2', return_value=device) as mock_cls:
            src = QPicameraSource(cameraID=1)
        mock_cls.assert_called_once_with(camera_num=1)
        src.source.close()


if __name__ == '__main__':
    unittest.main()
