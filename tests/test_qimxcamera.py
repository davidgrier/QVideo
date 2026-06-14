'''Unit tests for QIMXCamera and QIMXSource.'''
import sys
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtWidgets, QtCore, QtTest

from QVideo.cameras.Picamera._imx500 import QIMXCamera, QIMXSource

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_MODULE = sys.modules['QVideo.cameras.Picamera._imx500']
_CAMERA_MODULE = sys.modules['QVideo.cameras.Picamera._camera']

_FRAME_RGB = np.zeros((960, 1280, 3), dtype=np.uint8)

_CAMERA_CONTROLS = {
    'AeEnable':            (False, True,      True),
    'AwbEnable':           (False, True,      True),
    'Brightness':          (-1.0,  1.0,       0.0),
    'Contrast':            (0.0,   32.0,      1.0),
    'Saturation':          (0.0,   32.0,      1.0),
    'Sharpness':           (0.0,   16.0,      1.0),
    'ExposureTime':        (100,   1000000,   10000),
    'AnalogueGain':        (1.0,   16.0,      1.0),
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

_OUTPUTS = [np.array([0.9]), np.array([[10, 20, 100, 200]]), np.array([0])]


class MockTransform:
    def __init__(self, hflip=False, vflip=False):
        self.hflip = hflip
        self.vflip = vflip


def make_mock_imx500(outputs=_OUTPUTS, capture_ok=True):
    '''Return a MagicMock standing in for an IMX500 instance.'''
    device = MagicMock()
    device.camera_controls = _CAMERA_CONTROLS.copy()
    device.camera_config = {'main': {'size': (1280, 960), 'format': 'RGB888'}}
    device.global_camera_info.return_value = [{'Model': 'imx500'}]
    device.get_outputs.return_value = outputs
    if capture_ok:
        device.capture_array.return_value = _FRAME_RGB.copy()
        request = MagicMock()
        request.make_array.return_value = _FRAME_RGB.copy()
        request.get_metadata.return_value = _METADATA.copy()
        device.capture_request.return_value = request
    else:
        device.capture_array.side_effect = RuntimeError('no frame')
        device.capture_request.side_effect = RuntimeError('no frame')
    device.capture_metadata.return_value = _METADATA.copy()
    return device


def make_camera(model='/fake/model.rpk', outputs=_OUTPUTS, capture_ok=True):
    '''Return a QIMXCamera with a mocked IMX500 device.'''
    device = make_mock_imx500(outputs=outputs, capture_ok=capture_ok)
    with patch.object(_MODULE, 'IMX500', return_value=device), \
            patch.object(_CAMERA_MODULE, 'Transform', MockTransform):
        cam = QIMXCamera(model=model)
    return cam, device


class TestAll(unittest.TestCase):

    def test_all_defined(self):
        self.assertTrue(hasattr(_MODULE, '__all__'))

    def test_all_contains_qimxcamera(self):
        self.assertIn('QIMXCamera', _MODULE.__all__)

    def test_all_contains_qimxsource(self):
        self.assertIn('QIMXSource', _MODULE.__all__)


class TestInheritance(unittest.TestCase):

    def test_is_qpicamera_subclass(self):
        from QVideo.cameras.Picamera._camera import QPicamera
        cam, _ = make_camera()
        self.assertIsInstance(cam, QPicamera)
        cam.close()

    def test_has_new_output_signal(self):
        self.assertTrue(hasattr(QIMXCamera, 'newOutput'))


class TestInit(unittest.TestCase):

    def test_opens_on_init(self):
        cam, _ = make_camera()
        self.assertTrue(cam.isOpen())
        cam.close()

    def test_model_stored(self):
        cam, _ = make_camera(model='/my/model.rpk')
        self.assertEqual(cam._model, '/my/model.rpk')
        cam.close()

    def test_model_name_is_rpi_ai_camera(self):
        cam, _ = make_camera()
        self.assertEqual(cam.model_name, 'RPi AI Camera')
        cam.close()


class TestCreateDevice(unittest.TestCase):

    def test_imx500_called_with_model_and_camera_num(self):
        device = make_mock_imx500()
        with patch.object(_MODULE, 'IMX500') as MockIMX500, \
                patch.object(_CAMERA_MODULE, 'Transform', MockTransform):
            MockIMX500.return_value = device
            cam = QIMXCamera(model='/fake/model.rpk', cameraID=0)
        MockIMX500.assert_called_once_with('/fake/model.rpk', camera_num=0)
        cam.close()

    def test_returns_none_when_imx500_unavailable(self):
        with patch.object(_MODULE, 'IMX500', None), \
                patch.object(_CAMERA_MODULE, 'Transform', MockTransform):
            with self.assertLogs('QVideo.cameras.Picamera._imx500',
                                 level='WARNING'):
                cam = QIMXCamera.__new__(QIMXCamera)
                cam._model = '/fake/model.rpk'
                cam._cameraID = 0
                from QVideo.lib.QCamera import QCamera
                QCamera.__init__(cam)
                result = cam._createDevice()
        self.assertIsNone(result)

    def test_initialize_fails_when_imx500_unavailable(self):
        with patch.object(_MODULE, 'IMX500', None), \
                patch.object(_CAMERA_MODULE, 'Transform', MockTransform):
            with self.assertLogs('QVideo.cameras.Picamera._imx500',
                                 level='WARNING'):
                cam = QIMXCamera(model='/fake/model.rpk')
        self.assertFalse(cam.isOpen())


class TestNewOutput(unittest.TestCase):

    def test_new_output_emitted_on_read(self):
        cam, _ = make_camera()
        spy = QtTest.QSignalSpy(cam.newOutput)
        cam.read()
        self.assertEqual(len(spy), 1)
        cam.close()

    def test_new_output_value_matches_get_outputs(self):
        cam, device = make_camera(outputs=_OUTPUTS)
        spy = QtTest.QSignalSpy(cam.newOutput)
        cam.read()
        emitted = spy[0][0]
        self.assertEqual(len(emitted), len(_OUTPUTS))
        cam.close()

    def test_new_output_none_when_get_outputs_returns_none(self):
        cam, device = make_camera(outputs=None)
        spy = QtTest.QSignalSpy(cam.newOutput)
        cam.read()
        self.assertEqual(len(spy), 1)
        self.assertIsNone(spy[0][0])
        cam.close()

    def test_new_output_not_emitted_on_failed_read(self):
        cam, _ = make_camera(capture_ok=False)
        # Re-open with capture_ok=False to test failed read
        cam.close()
        device = make_mock_imx500(capture_ok=False)
        with patch.object(_MODULE, 'IMX500', return_value=device), \
                patch.object(_CAMERA_MODULE, 'Transform', MockTransform):
            cam2 = QIMXCamera(model='/fake/model.rpk')
        cam2.close()
        spy = QtTest.QSignalSpy(cam2.newOutput)
        cam2._isOpen = True  # force isOpen() to pass
        cam2._deviceOpen = True
        cam2._device = device
        cam2.read()
        self.assertEqual(len(spy), 0)
        cam2._isOpen = False

    def test_frame_still_returned_alongside_output(self):
        cam, _ = make_camera()
        success, frame = cam.read()
        self.assertTrue(success)
        self.assertIsNotNone(frame)
        cam.close()


class TestQIMXSource(unittest.TestCase):

    def test_creates_camera_when_none_given(self):
        device = make_mock_imx500()
        with patch.object(_MODULE, 'IMX500', return_value=device), \
                patch.object(_CAMERA_MODULE, 'Transform', MockTransform):
            source = QIMXSource(model='/fake/model.rpk')
        self.assertIsInstance(source.source, QIMXCamera)
        source.source.close()

    def test_uses_provided_camera(self):
        cam, _ = make_camera()
        source = QIMXSource(camera=cam)
        self.assertIs(source.source, cam)
        cam.close()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
