'''Unit tests for QOpenCVCamera.'''
import tempfile
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtWidgets, QtCore
from QVideo.tests.signals import record
from QVideo.cameras.OpenCV._camera import QOpenCVCamera
import QVideo.cameras.OpenCV._devices as _devices_module
from QVideo.cameras.OpenCV._devices import CameraDevice, QOpenCVDevices
from QVideo.lib.errors import QDeviceError


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME_BGR = np.zeros((480, 640, 3), dtype=np.uint8)
_FRAME_GRAY = np.zeros((480, 640), dtype=np.uint8)


def make_mock_device(width=640, height=480, fps=30.,
                     read_ok=True, frame=None):
    '''Return a MagicMock standing in for cv2.VideoCapture.'''
    if frame is None:
        frame = _FRAME_BGR.copy()
    device = MagicMock()
    device.read.return_value = (read_ok, frame)

    def _get(prop):
        return {QOpenCVCamera.WIDTH: width,
                QOpenCVCamera.HEIGHT: height,
                QOpenCVCamera.FPS: fps}.get(prop, 0)

    device.get.side_effect = _get
    return device


def make_camera(cameraID=0, mirrored=False, flipped=False, gray=False,
                width=640, height=480, fps=30.,
                read_ok=True, frame=None, formats=None):
    '''Return a QOpenCVCamera with a mocked VideoCapture device.

    *width*, *height*, and *fps* control the values the mock device
    returns from ``get()`` — they do not configure the camera itself.
    ``configure`` and ``probe_formats`` are patched for isolation;
    *formats* is what ``probe_formats`` returns (default: one format
    matching the device).
    '''
    if formats is None:
        formats = [(width, height, 1., fps)]
    device = make_mock_device(width=width, height=height, fps=fps,
                              read_ok=read_ok, frame=frame)
    with patch('cv2.VideoCapture', return_value=device):
        with patch('QVideo.cameras.OpenCV._camera.configure'):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                       return_value=formats):
                cam = QOpenCVCamera(cameraID=cameraID, mirrored=mirrored,
                                    flipped=flipped, gray=gray)
    return cam


_FORMATS = [(640, 480, 1., 30.), (1280, 720, 1., 30.),
            (1552, 1552, 1., 30.), (1920, 1080, 1., 15.)]


class TestGetResolution(unittest.TestCase):
    '''The resolution property reports the format nearest the device.'''

    def _label_at(self, width, height):
        cam = make_camera(formats=_FORMATS)
        cam._device.get.side_effect = lambda prop: {
            QOpenCVCamera.WIDTH: width,
            QOpenCVCamera.HEIGHT: height,
            QOpenCVCamera.FPS: 30.}.get(prop, 0)
        return cam._getResolution()

    def test_listed_size_returns_its_own_label(self):
        for w, h, _min, fps in _FORMATS:
            with self.subTest(size=(w, h)):
                self.assertEqual(self._label_at(w, h),
                                 f'{w}\u00d7{h} @ {fps:.0f} Hz')

    def test_unlisted_size_returns_the_nearest_format(self):
        self.assertEqual(self._label_at(1920, 1200), '1920\u00d71080 @ 15 Hz')

    def test_unlisted_size_between_formats_returns_the_nearer(self):
        self.assertEqual(self._label_at(1300, 700), '1280\u00d7720 @ 30 Hz')

    def test_nearest_is_not_always_the_smallest_format(self):
        self.assertNotEqual(self._label_at(1800, 1000),
                            '640\u00d7480 @ 30 Hz')

    def test_result_is_always_one_of_the_limits(self):
        cam = make_camera(formats=_FORMATS)
        for size in ((10, 10), (5000, 4000), (1000, 1000)):
            with self.subTest(size=size):
                cam._device.get.side_effect = lambda prop, s=size: {
                    QOpenCVCamera.WIDTH: s[0],
                    QOpenCVCamera.HEIGHT: s[1]}.get(prop, 0)
                self.assertIn(cam._getResolution(),
                              cam.properties['resolution']['limits'])


class TestInit(unittest.TestCase):

    def test_camera_id_stored(self):
        cam = make_camera()
        self.assertEqual(cam._cameraID, 0)

    def test_custom_camera_id(self):
        cam = make_camera(cameraID=2)
        self.assertEqual(cam._cameraID, 2)

    def test_opens_on_init(self):
        cam = make_camera()
        self.assertTrue(cam.isOpen())

    def test_default_mirrored_false(self):
        cam = make_camera()
        self.assertFalse(cam.mirrored)

    def test_default_flipped_false(self):
        cam = make_camera()
        self.assertFalse(cam.flipped)

    def test_default_color_true(self):
        cam = make_camera()
        self.assertTrue(cam.color)

    def test_mirrored_kwarg(self):
        cam = make_camera(mirrored=True)
        self.assertTrue(cam.mirrored)

    def test_flipped_kwarg(self):
        cam = make_camera(flipped=True)
        self.assertTrue(cam.flipped)

    def test_gray_kwarg_sets_color_false(self):
        cam = make_camera(gray=True)
        self.assertFalse(cam.color)

    def test_name_is_class_name(self):
        cam = make_camera()
        self.assertEqual(cam.name, 'QOpenCVCamera')


class TestInitialize(unittest.TestCase):

    def test_uses_v4l2_on_linux(self):
        import cv2
        device = make_mock_device()
        with patch('platform.system', return_value='Linux'):
            with patch('cv2.VideoCapture', return_value=device) as mock_cap:
                with patch('QVideo.cameras.OpenCV._camera.configure'):
                    with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                               return_value=[(640, 480, 1., 30.)]):
                        QOpenCVCamera()
        mock_cap.assert_called_with(0, cv2.CAP_V4L2)

    def test_uses_avfoundation_on_macos(self):
        import cv2
        device = make_mock_device()
        with patch('platform.system', return_value='Darwin'):
            with patch('cv2.VideoCapture', return_value=device) as mock_cap:
                with patch('QVideo.cameras.OpenCV._camera.configure'):
                    with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                               return_value=[(640, 480, 1., 30.)]):
                        QOpenCVCamera()
        mock_cap.assert_called_with(0, cv2.CAP_AVFOUNDATION)

    def test_uses_msmf_on_windows(self):
        import cv2
        device = make_mock_device()
        with patch('platform.system', return_value='Windows'):
            with patch('cv2.VideoCapture', return_value=device) as mock_cap:
                with patch('QVideo.cameras.OpenCV._camera.configure'):
                    with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                               return_value=[(640, 480, 1., 30.)]):
                        QOpenCVCamera()
        mock_cap.assert_called_with(0, cv2.CAP_MSMF)

    def test_uses_cap_any_on_other_platforms(self):
        import cv2
        device = make_mock_device()
        with patch('platform.system', return_value='Java'):
            with patch('cv2.VideoCapture', return_value=device) as mock_cap:
                with patch('QVideo.cameras.OpenCV._camera.configure'):
                    with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                               return_value=[(640, 480, 1., 30.)]):
                        QOpenCVCamera()
        mock_cap.assert_called_with(0, cv2.CAP_ANY)

    def test_initialize_fails_if_no_frame(self):
        with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
            cam = make_camera(read_ok=False)
        self.assertFalse(cam.isOpen())

    def test_device_released_when_initialize_fails(self):
        device = make_mock_device(read_ok=False)
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.configure'):
                with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                           return_value=[(640, 480, 1., 30.)]):
                    with self.assertLogs(
                            'QVideo.lib.QCamera', level='WARNING'):
                        QOpenCVCamera()
        device.release.assert_called_once()

    def test_device_properties_registered_on_open(self):
        cam = make_camera()
        for name in ('width', 'height', 'fps', 'color'):
            self.assertIn(name, cam.properties)

    def test_transform_properties_registered_before_open(self):
        # mirrored/flipped are registered in __init__, not _initialize
        device = make_mock_device(read_ok=False)
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.configure'):
                with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                           return_value=[(640, 480, 1., 30.)]):
                    with self.assertLogs(
                            'QVideo.lib.QCamera', level='WARNING'):
                        cam = QOpenCVCamera()
        for name in ('mirrored', 'flipped'):
            self.assertIn(name, cam.properties)

    def test_configure_called_with_default_params(self):
        '''Default constructor passes None, None, 30. to configure.'''
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.configure') as mock_cfg:
                with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                           return_value=[(640, 480, 1., 30.)]):
                    QOpenCVCamera()
        mock_cfg.assert_called_once_with(device, None, None, 30.,
                                         resolutions=[(640, 480)])

    def test_configure_called_with_explicit_width_height_fps(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.configure') as mock_cfg:
                with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                           return_value=[(640, 480, 1., 30.)]):
                    QOpenCVCamera(width=1280, height=720, fps=15.)
        mock_cfg.assert_called_once_with(device, 1280, 720, 15.,
                                         resolutions=[(640, 480)])

    def test_configure_called_with_performance_mode(self):
        '''fps=None triggers performance (slo-mo) mode.'''
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.configure') as mock_cfg:
                with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                           return_value=[(640, 480, 1., 30.)]):
                    QOpenCVCamera(fps=None)
        mock_cfg.assert_called_once_with(device, None, None, None,
                                         resolutions=[(640, 480)])


class TestDeinitialize(unittest.TestCase):

    def test_close_releases_device(self):
        cam = make_camera()
        device = cam._device
        cam.close()
        device.release.assert_called_once()

    def test_isopen_false_after_close(self):
        cam = make_camera()
        cam.close()
        self.assertFalse(cam.isOpen())


class TestProperties(unittest.TestCase):

    def test_width_via_attribute(self):
        cam = make_camera(width=640)
        self.assertEqual(cam.width, 640)

    def test_height_via_attribute(self):
        cam = make_camera(height=480)
        self.assertEqual(cam.height, 480)

    def test_fps_returns_float(self):
        cam = make_camera(fps=30.)
        self.assertIsInstance(cam.fps, float)
        self.assertAlmostEqual(cam.fps, 30.)

    def test_width_setter_updates_config(self):
        cam = make_camera()
        cam.set('width', 1280)
        self.assertEqual(cam._configWidth, 1280)

    def test_width_setter_calls_device_set(self):
        cam = make_camera()
        cam._device.set.reset_mock()
        cam.set('width', 1280)
        cam._device.set.assert_any_call(QOpenCVCamera.WIDTH, 1280)

    def tracking(self, cam):
        '''Make the mock device report what it was last asked for.'''
        values = {QOpenCVCamera.WIDTH: 640, QOpenCVCamera.HEIGHT: 480}
        cam._device.get.side_effect = lambda prop: values.get(prop, 0)
        cam._device.set.side_effect = \
            lambda prop, value: values.__setitem__(prop, value)

    def test_a_new_width_announces_the_new_shape(self):
        cam = make_camera()
        self.tracking(cam)
        spy = record(cam.shapeChanged)
        cam.set('width', 1280)
        self.assertEqual(spy, [(QtCore.QSize(1280, 480),)])

    def test_the_same_width_announces_nothing(self):
        cam = make_camera()
        self.tracking(cam)
        spy = record(cam.shapeChanged)
        cam.set('width', 640)
        self.assertEqual(spy, [])

    def test_a_new_resolution_announces_the_new_shape_once(self):
        cam = make_camera(formats=[(640, 480, 1., 30.), (1280, 720, 1., 30.)])
        self.tracking(cam)
        spy = record(cam.shapeChanged)
        label = [name for name, (w, h, _) in cam._formatLabels.items()
                 if (w, h) == (1280, 720)][0]
        cam.set('resolution', label)
        self.assertEqual(spy, [(QtCore.QSize(1280, 720),)])

    def test_height_setter_updates_config(self):
        cam = make_camera()
        cam.set('height', 720)
        self.assertEqual(cam._configHeight, 720)

    def test_height_setter_calls_device_set(self):
        cam = make_camera()
        cam._device.set.reset_mock()
        cam.set('height', 720)
        cam._device.set.assert_any_call(QOpenCVCamera.HEIGHT, 720)

    def test_a_new_height_announces_the_new_shape(self):
        cam = make_camera()
        self.tracking(cam)
        spy = record(cam.shapeChanged)
        cam.set('height', 720)
        self.assertEqual(spy, [(QtCore.QSize(640, 720),)])

    def test_fps_setter_calls_device_set(self):
        cam = make_camera()
        cam.set('fps', 60.)
        cam._device.set.assert_any_call(QOpenCVCamera.FPS, 60.)

    def test_fps_setter_updates_config(self):
        cam = make_camera()
        cam.set('fps', 60.)
        self.assertAlmostEqual(cam._configFps, 60.)

    def test_color_true_when_not_gray(self):
        cam = make_camera(gray=False)
        self.assertTrue(cam.color)

    def test_color_false_when_gray(self):
        cam = make_camera(gray=True)
        self.assertFalse(cam.color)

    def test_color_setter_updates_gray_state(self):
        cam = make_camera()
        cam.set('color', False)
        self.assertFalse(cam.color)
        self.assertTrue(cam._gray)

    def test_mirrored_setter(self):
        cam = make_camera()
        cam.set('mirrored', True)
        self.assertTrue(cam.mirrored)

    def test_flipped_setter(self):
        cam = make_camera()
        cam.set('flipped', True)
        self.assertTrue(cam.flipped)

    def test_all_properties_registered(self):
        cam = make_camera()
        for name in ('resolution', 'width', 'height', 'fps', 'color',
                     'mirrored', 'flipped'):
            self.assertIn(name, cam.properties)

    def test_resolution_registered_when_formats_available(self):
        cam = make_camera(width=640, height=480, fps=30.)
        self.assertIn('resolution', cam.properties)

    def test_resolution_not_registered_without_formats(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device), \
             patch('QVideo.cameras.OpenCV._camera.configure'), \
             patch('QVideo.cameras.OpenCV._camera.probe_formats',
                   return_value=[]):
            cam = QOpenCVCamera()
        self.assertNotIn('resolution', cam.properties)

    def test_resolution_getter_returns_label(self):
        cam = make_camera(width=640, height=480, fps=30.)
        label = cam._getResolution()
        self.assertIn('640', label)
        self.assertIn('480', label)

    def test_resolution_limits_match_formats(self):
        cam = make_camera(width=640, height=480, fps=30.)
        limits = cam.properties['resolution']['limits']
        self.assertEqual(len(limits), len(cam._formats))
        for label in limits:
            self.assertIn(label, cam._formatLabels)

    def test_resolution_setter_updates_width_height_fps(self):
        cam = make_camera(width=640, height=480, fps=30.)
        label = next(iter(cam._formatLabels))
        w, h, fps = cam._formatLabels[label]
        cam._device.set.reset_mock()
        cam._setResolution(label)
        cam._device.set.assert_any_call(QOpenCVCamera.WIDTH, w)
        cam._device.set.assert_any_call(QOpenCVCamera.HEIGHT, h)
        cam._device.set.assert_any_call(QOpenCVCamera.FPS, fps)

    def test_resolution_attribute_assignment(self):
        cam = make_camera(width=640, height=480, fps=30.)
        label = next(iter(cam._formatLabels))
        cam._device.set.reset_mock()
        cam.resolution = label
        cam._device.set.assert_any_call(
            QOpenCVCamera.WIDTH, cam._formatLabels[label][0])

    def test_width_height_fps_hidden_when_resolution_available(self):
        cam = make_camera(width=640, height=480, fps=30.)
        for name in ('width', 'height', 'fps'):
            with self.subTest(name=name):
                if name in cam.properties:
                    self.assertTrue(cam.properties[name].get('hidden', False))

    def test_width_height_not_hidden_without_formats(self):
        device = make_mock_device()
        with patch('cv2.VideoCapture', return_value=device), \
             patch('QVideo.cameras.OpenCV._camera.configure'), \
             patch('QVideo.cameras.OpenCV._camera.probe_formats',
                   return_value=[]):
            cam = QOpenCVCamera()
        for name in ('width', 'height'):
            with self.subTest(name=name):
                if name in cam.properties:
                    self.assertFalse(
                        cam.properties[name].get('hidden', False))


class TestRead(unittest.TestCase):

    def test_read_when_closed_returns_false_none(self):
        cam = make_camera()
        cam.close()
        success, frame = cam.read()
        self.assertFalse(success)
        self.assertIsNone(frame)

    def test_read_returns_frame_on_success(self):
        cam = make_camera()
        success, frame = cam.read()
        self.assertTrue(success)
        self.assertIsInstance(frame, np.ndarray)

    def test_read_color_frame_converted_to_rgb(self):
        cam = make_camera()
        with patch('cv2.cvtColor', return_value=_FRAME_BGR) as mock_cvt:
            cam.read()
        mock_cvt.assert_called_once()
        _, code = mock_cvt.call_args[0]
        self.assertEqual(code, QOpenCVCamera.BGR2RGB)

    def test_read_color_frame_converted_to_gray(self):
        cam = make_camera(gray=True)
        with patch('cv2.cvtColor', return_value=_FRAME_GRAY) as mock_cvt:
            cam.read()
        mock_cvt.assert_called_once()
        _, code = mock_cvt.call_args[0]
        self.assertEqual(code, QOpenCVCamera.BGR2GRAY)

    def test_read_grayscale_frame_not_converted(self):
        cam = make_camera(frame=_FRAME_GRAY.copy())
        with patch('cv2.cvtColor') as mock_cvt:
            cam.read()
        mock_cvt.assert_not_called()

    def test_read_mirrored(self):
        cam = make_camera(mirrored=True)
        with patch('cv2.cvtColor', return_value=_FRAME_BGR):
            with patch('cv2.flip', return_value=_FRAME_BGR) as mock_flip:
                cam.read()
        mock_flip.assert_called_once()
        self.assertEqual(mock_flip.call_args[0][1], 1)

    def test_read_flipped(self):
        cam = make_camera(flipped=True)
        with patch('cv2.cvtColor', return_value=_FRAME_BGR):
            with patch('cv2.flip', return_value=_FRAME_BGR) as mock_flip:
                cam.read()
        mock_flip.assert_called_once()
        self.assertEqual(mock_flip.call_args[0][1], 0)

    def test_read_mirrored_and_flipped(self):
        cam = make_camera(mirrored=True, flipped=True)
        with patch('cv2.cvtColor', return_value=_FRAME_BGR):
            with patch('cv2.flip', return_value=_FRAME_BGR) as mock_flip:
                cam.read()
        mock_flip.assert_called_once()
        self.assertEqual(mock_flip.call_args[0][1], -1)

    def test_read_device_exception_returns_false_none(self):
        cam = make_camera()
        cam._device.read.side_effect = RuntimeError('device error')
        with self.assertLogs('QVideo.cameras.OpenCV._camera', level='WARNING'):
            success, frame = cam.read()
        self.assertFalse(success)
        self.assertIsNone(frame)

    def test_read_no_flip_when_neither_set(self):
        cam = make_camera()
        with patch('cv2.cvtColor', return_value=_FRAME_BGR):
            with patch('cv2.flip') as mock_flip:
                cam.read()
        mock_flip.assert_not_called()


class TestProbeProperties(unittest.TestCase):

    def test_unsupported_property_not_registered(self):
        '''device.set returning False skips registration.'''
        device = make_mock_device()
        device.set.return_value = False
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                              return_value=[(640, 480, 1., 30.)]):
                cam = QOpenCVCamera()
        for name in ('fps', 'brightness', 'contrast'):
            self.assertNotIn(name, cam.properties)

    def test_supported_property_registered(self):
        '''device.set returning True registers the property.'''
        device = make_mock_device()
        device.set.return_value = True
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                              return_value=[(640, 480, 1., 30.)]):
                cam = QOpenCVCamera()
        self.assertIn('fps', cam.properties)

    def test_negative_get_value_skips_without_calling_set(self):
        '''OpenCV 5 reports an unsupported property as get() < 0.'''
        import cv2
        device = make_mock_device()
        device.get.side_effect = lambda prop: {
            QOpenCVCamera.WIDTH: 640,
            QOpenCVCamera.HEIGHT: 480,
            QOpenCVCamera.FPS: 30.,
        }.get(prop, -1)
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                              return_value=[(640, 480, 1., 30.)]):
                cam = QOpenCVCamera()
        self.assertNotIn('brightness', cam.properties)
        set_props = [c.args[0] for c in device.set.call_args_list]
        self.assertNotIn(cv2.CAP_PROP_BRIGHTNESS, set_props)

    def test_negative_exposure_value_still_probed(self):
        '''exposure is exempt from the get() < 0 fast path (log2 scale).'''
        device = make_mock_device()
        device.get.side_effect = lambda prop: {
            QOpenCVCamera.WIDTH: 640,
            QOpenCVCamera.HEIGHT: 480,
            QOpenCVCamera.FPS: 30.,
        }.get(prop, -1)
        device.set.return_value = True
        with patch('cv2.VideoCapture', return_value=device):
            with patch('QVideo.cameras.OpenCV._camera.probe_formats',
                              return_value=[(640, 480, 1., 30.)]):
                cam = QOpenCVCamera()
        self.assertIn('exposure', cam.properties)





class TestDeviceNames(unittest.TestCase):

    def test_the_system_lists_the_cameras(self):
        with patch('QVideo.cameras.OpenCV._camera.QOpenCVDevices.cameras',
                   return_value=[(0, 'Front'), (1, 'Back')]):
            self.assertEqual(QOpenCVCamera.deviceNames(),
                             {0: 'Front', 1: 'Back'})



class TestLoss(unittest.TestCase):
    '''A webcam that sends no frame for long is lost; a file never is.'''

    def silent(self, camera, seconds=10.):
        '''The camera has sent nothing for *seconds*, and fails its reads.'''
        camera._device.read.return_value = (False, None)
        camera._lastFrame -= seconds

    def lose(self, camera):
        with self.assertLogs('QVideo.lib.QCamera', 'ERROR'):
            return camera.saferead()

    def test_a_camera_that_sends_nothing_for_long_is_lost(self):
        camera = make_camera()
        lost = record(camera.lost)
        self.silent(camera)
        self.assertEqual(self.lose(camera), (False, None))
        self.assertFalse(camera.isOpen())
        self.assertEqual(len(lost), 1)
        self.assertIn('no frame for 10 s', lost[0][0])

    def test_it_says_so_once(self):
        camera = make_camera()
        lost = record(camera.lost)
        self.silent(camera)
        self.lose(camera)
        camera.saferead()
        camera.saferead()
        self.assertEqual(len(lost), 1)

    def test_a_short_silence_is_not_a_loss(self):
        camera = make_camera()
        lost = record(camera.lost)
        self.silent(camera, seconds=0.5)
        self.assertEqual(camera.saferead(), (False, None))
        self.assertTrue(camera.isOpen())
        self.assertEqual(lost, [])

    def test_a_frame_starts_the_clock_again(self):
        camera = make_camera()
        self.silent(camera, seconds=1.9)
        camera._device.read.return_value = (True, _FRAME_BGR.copy())
        self.assertTrue(camera.saferead()[0])
        camera._device.read.return_value = (False, None)
        camera._lastFrame -= 1.9            # 3.8 s in all, but not in a row
        camera.saferead()
        self.assertTrue(camera.isOpen())

    def test_a_read_that_raises_counts_as_silence(self):
        camera = make_camera()
        camera._device.read.side_effect = RuntimeError('gone')
        camera._lastFrame -= 10.
        with self.assertLogs('QVideo.lib.QCamera', 'ERROR'):
            with self.assertLogs('QVideo.cameras.OpenCV._camera', 'WARNING'):
                camera.saferead()
        self.assertFalse(camera.isOpen())

    def test_a_camera_that_the_system_closed_is_lost_at_once(self):
        camera = make_camera()
        camera._device.read.return_value = (False, None)
        camera._device.isOpened.return_value = False
        with self.assertLogs('QVideo.lib.QCamera', 'ERROR') as logs:
            camera.saferead()
        self.assertIn('closed the camera', logs.output[0])

    def test_a_video_file_is_never_lost(self):
        with tempfile.NamedTemporaryFile(suffix='.avi') as video:
            camera = make_camera(cameraID=video.name)
            lost = record(camera.lost)
            self.silent(camera, seconds=3600.)          # the end of the file
            self.assertEqual(camera.saferead(), (False, None))
            self.assertTrue(camera.isOpen())
            self.assertEqual(lost, [])

    def test_a_network_stream_is_live(self):
        camera = make_camera(cameraID='rtsp://example.invalid/stream')
        self.silent(camera)
        self.lose(camera)
        self.assertFalse(camera.isOpen())

    def test_a_loss_timeout_of_none_never_says_so(self):
        camera = make_camera()
        camera.lossTimeout = None
        self.silent(camera, seconds=3600.)
        camera.saferead()
        self.assertTrue(camera.isOpen())

    def test_a_longer_timeout_is_kept(self):
        camera = make_camera()
        camera.lossTimeout = 30.
        self.silent(camera, seconds=10.)
        camera.saferead()
        self.assertTrue(camera.isOpen())

    def test_a_change_of_a_setting_starts_the_clock_again(self):
        camera = make_camera()
        self.silent(camera, seconds=10.)
        camera.set('color', False)
        camera.saferead()
        self.assertTrue(camera.isOpen())



class TestWhichCamera(unittest.TestCase):
    '''A camera is opened by what stays with it, not only by an index.'''

    CAMERAS = [CameraDevice(0, 'HD Pro Webcam C920', '0x1110000046d08e5'),
               CameraDevice(1, 'FaceTime HD Camera', '47B4B64B-7067'),
               CameraDevice(2, 'HD Pro Webcam C922', '0x1120000046d085c')]

    def resolve(self, spec):
        with patch.object(QOpenCVDevices, 'devices',
                          return_value=self.CAMERAS):
            return QOpenCVCamera._resolve(spec)

    def test_an_index_stands_for_itself(self):
        self.assertEqual(self.resolve(1), 1)

    def test_a_number_in_text_is_an_index(self):
        self.assertEqual(self.resolve('2'), 2)

    def test_a_unique_id_names_a_camera(self):
        self.assertEqual(self.resolve('0x1110000046d08e5'), 0)

    def test_a_part_of_a_name_names_a_camera(self):
        self.assertEqual(self.resolve('FaceTime'), 1)

    def test_an_address_is_not_looked_up(self):
        self.assertEqual(self.resolve('rtsp://example.invalid/s'),
                         'rtsp://example.invalid/s')

    def test_a_video_file_is_not_looked_up(self):
        with tempfile.NamedTemporaryFile(suffix='.avi') as video:
            self.assertEqual(self.resolve(video.name), video.name)

    def test_a_name_that_no_camera_has_is_refused_with_the_list(self):
        with self.assertRaises(QDeviceError) as caught:
            self.resolve('Logitech')
        message = str(caught.exception)
        self.assertIn("'Logitech'", message)
        self.assertIn('0: HD Pro Webcam C920', message)
        self.assertIn('1: FaceTime HD Camera', message)

    def test_a_name_that_two_cameras_have_is_refused(self):
        with self.assertRaises(QDeviceError):
            self.resolve('webcam')

    def test_the_camera_opens_the_index_that_the_name_stands_for(self):
        with patch.object(QOpenCVDevices, 'devices',
                          return_value=self.CAMERAS):
            camera = make_camera(cameraID='FaceTime')
        self.assertEqual(camera._cameraID, 1)

    def test_an_open_camera_knows_its_name_and_its_id(self):
        with patch.object(QOpenCVDevices, 'devices',
                          return_value=self.CAMERAS):
            camera = make_camera(cameraID=0)
        self.assertEqual(camera.modelName, 'HD Pro Webcam C920')
        self.assertEqual(camera.deviceID, '0x1110000046d08e5')

    def test_opening_a_camera_does_not_open_the_others_to_name_it(self):
        with patch.object(_devices_module, '_QMediaDevices', None):
            with patch.object(QOpenCVDevices, '_probe_cameras') as probe:
                camera = make_camera(cameraID=0)
        probe.assert_not_called()
        self.assertIsNone(camera.deviceID)

    def test_a_video_file_has_no_device_id(self):
        with tempfile.NamedTemporaryFile(suffix='.avi') as video:
            camera = make_camera(cameraID=video.name)
        self.assertIsNone(camera.deviceID)


if __name__ == '__main__':
    unittest.main()
