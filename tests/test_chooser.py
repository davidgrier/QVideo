'''Unit tests for chooser.py.'''
import unittest
from argparse import ArgumentParser
from unittest.mock import MagicMock, patch
import numpy as np
from pyqtgraph.Qt import QtWidgets
import QVideo.lib.chooser as chooser_module
from QVideo.lib.chooser import camera_parser, choose_camera, _CameraEntry, _CAMERAS

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME_BGR = np.zeros((480, 640, 3), dtype=np.uint8)


def make_mock_cv2_device(width=640, height=480, fps=30., read_ok=True):
    from QVideo.cameras.OpenCV.QOpenCVCamera import QOpenCVCamera
    device = MagicMock()
    device.read.return_value = (read_ok, _FRAME_BGR.copy())

    def _get(prop):
        return {QOpenCVCamera.WIDTH: width,
                QOpenCVCamera.HEIGHT: height,
                QOpenCVCamera.FPS: fps}.get(prop, 0)

    device.get.side_effect = _get
    return device


class TestChooserAll(unittest.TestCase):

    def test_all_is_defined(self):
        self.assertTrue(hasattr(chooser_module, '__all__'))

    def test_all_contains_camera_parser(self):
        self.assertIn('camera_parser', chooser_module.__all__)

    def test_all_contains_choose_camera(self):
        self.assertIn('choose_camera', chooser_module.__all__)

    def test_all_excludes_cameras_dict(self):
        self.assertNotIn('_CAMERAS', chooser_module.__all__)


class TestCameraEntry(unittest.TestCase):

    def test_is_named_tuple(self):
        entry = _CameraEntry('-x', 'mod', 'cls', 'label', 'help text')
        self.assertEqual(entry.flag, '-x')
        self.assertEqual(entry.module, 'mod')
        self.assertEqual(entry.cls, 'cls')
        self.assertEqual(entry.label, 'label')
        self.assertEqual(entry.help, 'help text')

    def test_cameras_dict_values_are_camera_entries(self):
        for entry in _CAMERAS.values():
            self.assertIsInstance(entry, _CameraEntry)

    def test_all_entries_have_non_empty_fields(self):
        for dest, entry in _CAMERAS.items():
            with self.subTest(dest=dest):
                self.assertTrue(all(entry))


class TestCameraParser(unittest.TestCase):

    def test_returns_argument_parser(self):
        self.assertIsInstance(camera_parser(), ArgumentParser)

    def test_accepts_existing_parser(self):
        parser = ArgumentParser()
        result = camera_parser(parser)
        self.assertIs(result, parser)

    def test_creates_new_parser_when_none(self):
        self.assertIsInstance(camera_parser(None), ArgumentParser)

    def test_default_cameraID_is_zero(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertEqual(args.cameraID, 0)

    def test_cameraID_positional_argument(self):
        args, _ = camera_parser().parse_known_args(['3'])
        self.assertEqual(args.cameraID, 3)

    def test_opencv_flag_false_by_default(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertFalse(args.opencv)

    def test_opencv_flag_set_by_minus_c(self):
        args, _ = camera_parser().parse_known_args(['-c'])
        self.assertTrue(args.opencv)

    def test_flir_flag_false_by_default(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertFalse(args.flir)

    def test_flir_flag_set_by_minus_f(self):
        args, _ = camera_parser().parse_known_args(['-f'])
        self.assertTrue(args.flir)

    def test_spinnaker_flag_false_by_default(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertFalse(args.spinnaker)

    def test_spinnaker_flag_set_by_minus_s(self):
        args, _ = camera_parser().parse_known_args(['-s'])
        self.assertTrue(args.spinnaker)

    def test_unknown_args_are_ignored(self):
        _, unknown = camera_parser().parse_known_args(['--unknown'])
        self.assertIn('--unknown', unknown)

    def test_camera_flags_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            camera_parser().parse_args(['-c', '-f'])

    def test_flags_match_cameras_dict(self):
        p = camera_parser()
        for dest, entry in _CAMERAS.items():
            with self.subTest(dest=dest):
                self.assertIn(entry.flag, p._option_string_actions)

    def test_does_not_duplicate_flags_on_existing_parser(self):
        parser = ArgumentParser()
        camera_parser(parser)
        camera_parser(parser)  # second call should not raise
        args, _ = parser.parse_known_args(['-c'])
        self.assertTrue(args.opencv)

    def test_does_not_duplicate_cameraID_on_existing_parser(self):
        parser = ArgumentParser()
        camera_parser(parser)
        camera_parser(parser)  # second call should not raise
        args, _ = parser.parse_known_args(['2'])
        self.assertEqual(args.cameraID, 2)


class TestChooseCameraDefault(unittest.TestCase):

    def test_defaults_to_noise_camera(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog']):
            camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        camera.close()

    def test_accepts_custom_parser(self):
        from QVideo.cameras.Noise import QNoiseTree
        parser = ArgumentParser()
        with patch('sys.argv', ['prog']):
            camera = choose_camera(parser)
        self.assertIsInstance(camera, QNoiseTree)
        camera.close()

    def test_noise_camera_accepts_cameraID(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '3']):
            camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        camera.close()


class TestChooseCameraOpenCV(unittest.TestCase):

    def test_opencv_flag_returns_opencv_camera(self):
        from QVideo.cameras.OpenCV import QOpenCVTree
        device = make_mock_cv2_device()
        with patch('sys.argv', ['prog', '-c']):
            with patch('cv2.VideoCapture', return_value=device):
                camera = choose_camera()
        self.assertIsInstance(camera, QOpenCVTree)
        camera.close()

    def test_opencv_flag_forwards_cameraID(self):
        from QVideo.cameras.OpenCV.QOpenCVCamera import QOpenCVCamera
        device = make_mock_cv2_device()
        with patch('sys.argv', ['prog', '-c', '2']):
            with patch('cv2.VideoCapture', return_value=device) as mock_cap:
                camera = choose_camera()
        args, _ = mock_cap.call_args
        self.assertEqual(args[0], 2)
        camera.close()

    def test_opencv_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-c']):
            with patch('QVideo.lib.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.OpenCV': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()


class TestChooseCameraFallback(unittest.TestCase):

    def test_flir_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-f']):
            with patch('QVideo.lib.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.Flir': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()

    def test_spinnaker_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-s']):
            with patch('QVideo.lib.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.Spinnaker': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()


if __name__ == '__main__':
    unittest.main()
