'''Unit tests for QOpenCVDevices.'''
import sys
import unittest
from unittest.mock import MagicMock, patch

import QVideo.cameras.OpenCV._devices as _devices_module
from QVideo.cameras.OpenCV._devices import (
    CameraDevice, QOpenCVDevices, capture_backend)


def make_mock_format(width, height, min_fps, max_fps):
    '''Return a mock QVideoFormat.'''
    fmt = MagicMock()
    size = MagicMock()
    size.width.return_value = width
    size.height.return_value = height
    fmt.resolution.return_value = size
    fmt.minFrameRate.return_value = min_fps
    fmt.maxFrameRate.return_value = max_fps
    return fmt


def make_mock_camera_device(device_id, description, formats):
    '''Return a mock QCameraDevice.

    Parameters
    ----------
    device_id : bytes
        Value returned by ``dev.id()``  (e.g. ``b'/dev/video0'``).
    description : str
        Human-readable camera name.
    formats : list of mock QVideoFormat
        Returned by ``dev.videoFormats()``.
    '''
    dev = MagicMock()
    dev.id.return_value = device_id
    dev.description.return_value = description
    dev.videoFormats.return_value = formats
    return dev


def make_mock_qmediadevices(devices):
    '''Return a mock QMediaDevices class with *devices* as video inputs.'''
    mock_cls = MagicMock()
    mock_cls.videoInputs.return_value = devices
    return mock_cls


class TestCaptureBackend(unittest.TestCase):

    def test_linux_uses_v4l2(self):
        import cv2
        with patch('platform.system', return_value='Linux'):
            self.assertEqual(capture_backend(), cv2.CAP_V4L2)

    def test_windows_uses_msmf(self):
        import cv2
        with patch('platform.system', return_value='Windows'):
            self.assertEqual(capture_backend(), cv2.CAP_MSMF)

    def test_darwin_uses_avfoundation(self):
        import cv2
        with patch('platform.system', return_value='Darwin'):
            self.assertEqual(capture_backend(), cv2.CAP_AVFOUNDATION)

    def test_other_platforms_use_cap_any(self):
        import cv2
        with patch('platform.system', return_value='Java'):
            self.assertEqual(capture_backend(), cv2.CAP_ANY)


class TestCameras(unittest.TestCase):

    def test_cameras_uses_qt_when_available(self):
        devs = [
            make_mock_camera_device(b'/dev/video0', 'Webcam A', []),
            make_mock_camera_device(b'/dev/video1', 'Webcam B', []),
        ]
        mock_qmd = make_mock_qmediadevices(devs)
        with patch.object(_devices_module, '_QMediaDevices', mock_qmd):
            result = QOpenCVDevices.cameras()
        self.assertEqual(result, [(0, 'Webcam A'), (1, 'Webcam B')])

    def test_cameras_falls_back_to_probe_when_no_qt(self):
        with patch.object(_devices_module, '_QMediaDevices', None):
            with patch.object(QOpenCVDevices, '_probe_cameras',
                              return_value=[(0, 'Camera 0')]) as mock_probe:
                result = QOpenCVDevices.cameras()
        mock_probe.assert_called_once()
        self.assertEqual(result, [(0, 'Camera 0')])

    def test_cameras_returns_list(self):
        mock_qmd = make_mock_qmediadevices([])
        with patch.object(_devices_module, '_QMediaDevices', mock_qmd):
            result = QOpenCVDevices.cameras()
        self.assertIsInstance(result, list)


class TestFormats(unittest.TestCase):

    def _make_devices_with_formats(self):
        fmts = [
            make_mock_format(640, 480, 5., 30.),
            make_mock_format(1280, 720, 5., 15.),
        ]
        dev = make_mock_camera_device(b'/dev/video0', 'Webcam', fmts)
        return [dev]

    def test_formats_uses_qt_resolutions_with_probed_fps(self):
        '''Qt provides the resolution list; fps is always probed via OpenCV.'''
        devices = self._make_devices_with_formats()
        mock_qmd = make_mock_qmediadevices(devices)
        probed = [(640, 480, 1., 30.), (1280, 720, 1., 15.)]
        with patch.object(_devices_module, '_QMediaDevices', mock_qmd):
            with patch('platform.system', return_value='Linux'):
                with patch.object(QOpenCVDevices, '_probe_formats',
                                  return_value=probed) as mock_probe:
                    result = QOpenCVDevices.formats(0)
        # Qt-sourced resolutions are passed to _probe_formats for fps probing
        mock_probe.assert_called_once_with(0, [(640, 480), (1280, 720)])
        self.assertEqual(result, probed)

    def test_formats_falls_back_when_no_qt(self):
        with patch.object(_devices_module, '_QMediaDevices', None):
            with patch.object(QOpenCVDevices, '_probe_formats',
                              return_value=[(640, 480, 1., 30.)]) as mock_probe:
                result = QOpenCVDevices.formats(0)
        mock_probe.assert_called_once_with(0, None)
        self.assertEqual(result, [(640, 480, 1., 30.)])

    def test_formats_falls_back_when_device_not_found(self):
        dev = make_mock_camera_device(b'/dev/video5', 'Other', [])
        mock_qmd = make_mock_qmediadevices([dev])
        with patch.object(_devices_module, '_QMediaDevices', mock_qmd):
            with patch('platform.system', return_value='Linux'):
                with patch.object(QOpenCVDevices, '_probe_formats',
                                  return_value=[]) as mock_probe:
                    QOpenCVDevices.formats(0)
        mock_probe.assert_called_once_with(0, None)

    def test_formats_returns_list(self):
        with patch.object(_devices_module, '_QMediaDevices', None):
            with patch.object(QOpenCVDevices, '_probe_formats',
                              return_value=[]):
                result = QOpenCVDevices.formats(0)
        self.assertIsInstance(result, list)


class TestFindDevice(unittest.TestCase):

    def test_linux_match_by_path(self):
        dev0 = make_mock_camera_device(b'/dev/video0', 'Cam0', [])
        dev1 = make_mock_camera_device(b'/dev/video1', 'Cam1', [])
        with patch('platform.system', return_value='Linux'):
            result = QOpenCVDevices._find_device(1, [dev0, dev1])
        self.assertIs(result, dev1)

    def test_linux_match_gstreamer_prefixed_id(self):
        '''Qt6/GStreamer backend reports IDs as b"v4l2:///dev/videoN".'''
        dev0 = make_mock_camera_device(b'v4l2:///dev/video0', 'Cam0', [])
        dev1 = make_mock_camera_device(b'v4l2:///dev/video1', 'Cam1', [])
        with patch('platform.system', return_value='Linux'):
            result = QOpenCVDevices._find_device(1, [dev0, dev1])
        self.assertIs(result, dev1)

    def test_linux_match_null_terminated_id(self):
        '''Handle QByteArray-to-bytes conversion that adds a null byte.'''
        dev0 = make_mock_camera_device(b'/dev/video0\x00', 'Cam0', [])
        with patch('platform.system', return_value='Linux'):
            result = QOpenCVDevices._find_device(0, [dev0])
        self.assertIs(result, dev0)

    def test_linux_no_match_returns_none(self):
        dev0 = make_mock_camera_device(b'/dev/video0', 'Cam0', [])
        with patch('platform.system', return_value='Linux'):
            result = QOpenCVDevices._find_device(5, [dev0])
        self.assertIsNone(result)

    def test_non_linux_match_by_index(self):
        dev0 = make_mock_camera_device(b'uid-0', 'Cam0', [])
        dev1 = make_mock_camera_device(b'uid-1', 'Cam1', [])
        with patch('platform.system', return_value='Darwin'):
            result = QOpenCVDevices._find_device(1, [dev0, dev1])
        self.assertIs(result, dev1)

    def test_non_linux_out_of_range_returns_none(self):
        dev0 = make_mock_camera_device(b'uid-0', 'Cam0', [])
        with patch('platform.system', return_value='Darwin'):
            result = QOpenCVDevices._find_device(5, [dev0])
        self.assertIsNone(result)

    def test_windows_match_by_index(self):
        dev0 = make_mock_camera_device(b'uid-0', 'Cam0', [])
        dev1 = make_mock_camera_device(b'uid-1', 'Cam1', [])
        with patch('platform.system', return_value='Windows'):
            result = QOpenCVDevices._find_device(0, [dev0, dev1])
        self.assertIs(result, dev0)


class TestFormatsFromDevice(unittest.TestCase):

    def test_single_format(self):
        fmts = [make_mock_format(640, 480, 5., 30.)]
        dev = make_mock_camera_device(b'', 'Cam', fmts)
        result = QOpenCVDevices._formats_from_device(dev)
        self.assertEqual(result, [(640, 480, 5., 30.)])

    def test_multiple_distinct_resolutions(self):
        fmts = [
            make_mock_format(640, 480, 5., 30.),
            make_mock_format(1280, 720, 5., 15.),
        ]
        dev = make_mock_camera_device(b'', 'Cam', fmts)
        result = QOpenCVDevices._formats_from_device(dev)
        self.assertEqual(len(result), 2)
        self.assertIn((640, 480, 5., 30.), result)
        self.assertIn((1280, 720, 5., 15.), result)

    def test_same_resolution_different_formats_merged(self):
        # Same resolution with different pixel formats → fps ranges merged
        fmts = [
            make_mock_format(640, 480, 5., 30.),
            make_mock_format(640, 480, 10., 60.),
        ]
        dev = make_mock_camera_device(b'', 'Cam', fmts)
        result = QOpenCVDevices._formats_from_device(dev)
        self.assertEqual(len(result), 1)
        w, h, lo, hi = result[0]
        self.assertEqual((w, h), (640, 480))
        self.assertAlmostEqual(lo, 5.)
        self.assertAlmostEqual(hi, 60.)

    def test_result_is_sorted(self):
        fmts = [
            make_mock_format(1920, 1080, 5., 30.),
            make_mock_format(320, 240, 5., 30.),
            make_mock_format(640, 480, 5., 30.),
        ]
        dev = make_mock_camera_device(b'', 'Cam', fmts)
        result = QOpenCVDevices._formats_from_device(dev)
        self.assertEqual(result, sorted(result))

    def test_empty_formats(self):
        dev = make_mock_camera_device(b'', 'Cam', [])
        result = QOpenCVDevices._formats_from_device(dev)
        self.assertEqual(result, [])


class TestProbeCameras(unittest.TestCase):

    def test_stops_at_first_closed_device(self):
        import cv2
        cap_ok = MagicMock()
        cap_ok.isOpened.return_value = True
        cap_fail = MagicMock()
        cap_fail.isOpened.return_value = False

        with patch('cv2.VideoCapture', side_effect=[cap_ok, cap_fail]):
            result = QOpenCVDevices._probe_cameras()
        self.assertEqual(result, [(0, 'Camera 0')])

    def test_returns_list_of_tuples(self):
        cap_fail = MagicMock()
        cap_fail.isOpened.return_value = False
        with patch('cv2.VideoCapture', return_value=cap_fail):
            result = QOpenCVDevices._probe_cameras()
        self.assertIsInstance(result, list)

    def test_empty_when_no_cameras(self):
        cap_fail = MagicMock()
        cap_fail.isOpened.return_value = False
        with patch('cv2.VideoCapture', return_value=cap_fail):
            result = QOpenCVDevices._probe_cameras()
        self.assertEqual(result, [])


class TestProbeFormats(unittest.TestCase):

    def test_returns_empty_when_device_not_opened(self):
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch('cv2.VideoCapture', return_value=cap):
            result = QOpenCVDevices._probe_formats(0)
        self.assertEqual(result, [])

    def test_uses_v4l2_on_linux(self):
        '''_probe_formats uses CAP_V4L2 on Linux to avoid GStreamer warnings.'''
        import cv2
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch('platform.system', return_value='Linux'):
            with patch('cv2.VideoCapture', return_value=cap) as mock_cap:
                QOpenCVDevices._probe_formats(0)
        mock_cap.assert_called_once_with(0, cv2.CAP_V4L2)

    def test_uses_avfoundation_on_darwin(self):
        import cv2
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch('platform.system', return_value='Darwin'):
            with patch('cv2.VideoCapture', return_value=cap) as mock_cap:
                QOpenCVDevices._probe_formats(0)
        mock_cap.assert_called_once_with(0, cv2.CAP_AVFOUNDATION)

    def test_uses_msmf_on_windows(self):
        import cv2
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch('platform.system', return_value='Windows'):
            with patch('cv2.VideoCapture', return_value=cap) as mock_cap:
                QOpenCVDevices._probe_formats(0)
        mock_cap.assert_called_once_with(0, cv2.CAP_MSMF)

    def test_uses_cap_any_elsewhere(self):
        import cv2
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch('platform.system', return_value='Java'):
            with patch('cv2.VideoCapture', return_value=cap) as mock_cap:
                QOpenCVDevices._probe_formats(0)
        mock_cap.assert_called_once_with(0, cv2.CAP_ANY)

    def test_delegates_to_probe_formats(self):
        '''_probe_formats passes the open device to probe_formats().'''
        cap = MagicMock()
        cap.isOpened.return_value = True
        expected = [(640, 480, 1., 30.), (1280, 720, 1., 15.)]
        with patch('cv2.VideoCapture', return_value=cap):
            with patch('QVideo.cameras.OpenCV._devices.probe_formats',
                       return_value=expected) as mock_pf:
                result = QOpenCVDevices._probe_formats(0)
        mock_pf.assert_called_once_with(cap, None)
        self.assertEqual(result, expected)

    def test_passes_resolutions_to_probe_formats(self):
        '''Resolution list from Qt is forwarded to probe_formats().'''
        cap = MagicMock()
        cap.isOpened.return_value = True
        res = [(640, 480), (1280, 720)]
        with patch('cv2.VideoCapture', return_value=cap):
            with patch('QVideo.cameras.OpenCV._devices.probe_formats',
                       return_value=[]) as mock_pf:
                QOpenCVDevices._probe_formats(0, res)
        mock_pf.assert_called_once_with(cap, res)

    def test_the_device_is_released_when_probing_fails(self):
        cap = MagicMock()
        cap.isOpened.return_value = True
        with patch('cv2.VideoCapture', return_value=cap):
            with patch('QVideo.cameras.OpenCV._devices.probe_formats',
                       side_effect=RuntimeError('driver error')):
                with self.assertRaises(RuntimeError):
                    QOpenCVDevices._probe_formats(0)
        cap.release.assert_called_once_with()

    def test_the_device_is_released_when_it_would_not_open(self):
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch('cv2.VideoCapture', return_value=cap):
            self.assertEqual(QOpenCVDevices._probe_formats(0), [])
        cap.release.assert_called_once_with()



def device(identifier, name='Cam'):
    return make_mock_camera_device(identifier, name, [])


class TestOrdered(unittest.TestCase):
    '''OpenCV does not number the cameras in the order that Qt lists them.'''

    def order(self, system, devices):
        with patch('platform.system', return_value=system):
            return QOpenCVDevices._ordered(devices)

    def test_macos_sorts_by_the_unique_id(self):
        # What a MacBook gave with a USB camera: Qt listed the built-in
        # camera first; OpenCV opened the USB camera as 0.
        builtin = device(b'47B4B64B-7067-4B9C-AD2B-AE273A71F4B5', 'FaceTime')
        usb = device(b'0x1110000046d08e5', 'C920')
        self.assertEqual(self.order('Darwin', [builtin, usb]),
                         [(0, usb), (1, builtin)])

    def test_macos_keeps_an_order_that_is_sorted(self):
        usb = device(b'0x1110000046d08e5')
        builtin = device(b'47B4B64B')
        self.assertEqual(self.order('Darwin', [usb, builtin]),
                         [(0, usb), (1, builtin)])

    def test_linux_takes_the_index_from_the_path(self):
        a = device(b'/dev/video0')
        b = device(b'/dev/video2')       # video1 is a metadata node
        self.assertEqual(self.order('Linux', [b, a]), [(0, a), (2, b)])

    def test_linux_leaves_out_a_device_without_a_video_path(self):
        a = device(b'/dev/video0')
        b = device(b'libcamera:something')
        self.assertEqual(self.order('Linux', [a, b]), [(0, a)])

    def test_linux_ids_of_the_gstreamer_backend_have_a_prefix(self):
        a = device(b'v4l2:///dev/video3')
        self.assertEqual(self.order('Linux', [a]), [(3, a)])

    def test_other_systems_keep_the_order_of_qt(self):
        a, b = device(b'z'), device(b'a')
        self.assertEqual(self.order('Windows', [a, b]), [(0, a), (1, b)])


class TestDevices(unittest.TestCase):

    def devices(self, system, qt):
        with patch('platform.system', return_value=system), \
             patch.object(_devices_module, '_QMediaDevices',
                          make_mock_qmediadevices(qt)):
            return QOpenCVDevices.devices()

    def test_a_device_has_an_index_a_name_and_an_id(self):
        result = self.devices('Linux', [device(b'/dev/video0', 'Webcam')])
        self.assertEqual(result, [CameraDevice(0, 'Webcam', '/dev/video0')])

    def test_the_prefix_of_the_gstreamer_backend_is_not_in_the_id(self):
        result = self.devices('Linux', [device(b'v4l2:///dev/video1', 'W')])
        self.assertEqual(result[0].id, '/dev/video1')

    def test_the_names_follow_the_indices_of_opencv(self):
        builtin = device(b'47B4B64B', 'FaceTime')
        usb = device(b'0x1110000046d08e5', 'C920')
        result = self.devices('Darwin', [builtin, usb])
        self.assertEqual([(d.index, d.name) for d in result],
                         [(0, 'C920'), (1, 'FaceTime')])

    def test_without_qt_the_cameras_have_no_id(self):
        with patch.object(_devices_module, '_QMediaDevices', None), \
             patch.object(QOpenCVDevices, '_probe_cameras',
                          return_value=[(0, 'Camera 0')]):
            result = QOpenCVDevices.devices()
        self.assertEqual(result, [CameraDevice(0, 'Camera 0', '')])

    def test_without_qt_and_without_probing_there_is_nothing_to_list(self):
        with patch.object(_devices_module, '_QMediaDevices', None), \
             patch.object(QOpenCVDevices, '_probe_cameras') as probe:
            self.assertEqual(QOpenCVDevices.devices(probe=False), [])
        probe.assert_not_called()

    def test_the_formats_are_those_of_the_camera_opencv_opens(self):
        # Index 0 is the USB camera on macOS, whatever Qt lists first.
        builtin = make_mock_camera_device(b'47B4B64B', 'FaceTime', [])
        usb = make_mock_camera_device(b'0x1110000046d08e5', 'C920', [])
        with patch('platform.system', return_value='Darwin'):
            self.assertIs(QOpenCVDevices._find_device(0, [builtin, usb]), usb)


class TestFind(unittest.TestCase):

    CAMERAS = [CameraDevice(0, 'HD Pro Webcam C920', '0x1110000046d08e5'),
               CameraDevice(1, 'FaceTime HD Camera', '47B4B64B-7067'),
               CameraDevice(2, 'HD Pro Webcam C922', '0x1120000046d085c')]

    def find(self, spec):
        with patch.object(QOpenCVDevices, 'devices',
                          return_value=self.CAMERAS):
            return QOpenCVDevices.find(spec)

    def test_an_index_that_exists(self):
        self.assertEqual(self.find(1), 1)

    def test_an_index_that_does_not_exist(self):
        self.assertIsNone(self.find(5))

    def test_a_unique_id(self):
        self.assertEqual(self.find('0x1120000046d085c'), 2)

    def test_an_id_is_not_case_sensitive(self):
        self.assertEqual(self.find('47b4b64b-7067'), 1)

    def test_a_part_of_a_name(self):
        self.assertEqual(self.find('facetime'), 1)
        self.assertEqual(self.find('C920'), 0)

    def test_a_part_of_a_name_that_two_cameras_have_is_refused(self):
        self.assertIsNone(self.find('webcam'))

    def test_nothing_matches_nothing(self):
        self.assertIsNone(self.find('no such camera'))
        self.assertIsNone(self.find(''))
        self.assertIsNone(self.find('   '))


if __name__ == '__main__':
    unittest.main()
