'''Unit tests for QOpenCVDevices.'''
import sys
import unittest
from unittest.mock import MagicMock, patch

import QVideo.cameras.OpenCV._devices as _devices_module
from QVideo.cameras.OpenCV._devices import QOpenCVDevices


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

    def test_uses_cap_any_on_non_linux(self):
        import cv2
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch('platform.system', return_value='Darwin'):
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


if __name__ == '__main__':
    unittest.main()
