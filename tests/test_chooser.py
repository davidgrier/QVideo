'''Unit tests for chooser.py.'''
import sys
import threading
import contextlib
import io
import unittest
from argparse import ArgumentParser
from unittest.mock import MagicMock, patch
import numpy as np
from qtpy import QtWidgets
import QVideo.cameras.chooser as chooser_module
from QVideo.lib.errors import QDriverError
from QVideo.cameras.chooser import (camera_parser, choose_camera, make_tree,
                                    open_camera, BACKENDS, _BackendEntry,
                                    _CAMERAS)

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME_BGR = np.zeros((480, 640, 3), dtype=np.uint8)


def make_mock_cv2_device(width=640, height=480, fps=30., read_ok=True):
    from QVideo.cameras.OpenCV._camera import QOpenCVCamera
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

    def test_the_flags_come_from_the_registry(self):
        self.assertEqual(set(_CAMERAS),
                         {k for k, e in BACKENDS.items() if e.flag})

    def test_cameras_dict_values_are_backend_entries(self):
        for entry in _CAMERAS.values():
            self.assertIsInstance(entry, _BackendEntry)

    def test_all_entries_have_a_flag_and_help(self):
        for dest, entry in _CAMERAS.items():
            with self.subTest(dest=dest):
                self.assertTrue(entry.flag and entry.help)

    def test_flags_are_unique(self):
        flags = [entry.flag for entry in _CAMERAS.values()]
        self.assertEqual(len(flags), len(set(flags)))

    def test_every_backend_but_noise_has_a_flag(self):
        self.assertEqual(set(BACKENDS) - set(_CAMERAS), {'noise'})


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

    def test_basler_flag_false_by_default(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertFalse(args.basler)

    def test_basler_flag_set_by_minus_b(self):
        args, _ = camera_parser().parse_known_args(['-b'])
        self.assertTrue(args.basler)

    def test_ids_flag_false_by_default(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertFalse(args.ids)

    def test_ids_flag_set_by_minus_i(self):
        args, _ = camera_parser().parse_known_args(['-i'])
        self.assertTrue(args.ids)

    def test_mv_flag_false_by_default(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertFalse(args.mv)

    def test_mv_flag_set_by_minus_m(self):
        args, _ = camera_parser().parse_known_args(['-m'])
        self.assertTrue(args.mv)

    def test_picamera_flag_false_by_default(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertFalse(args.picamera)

    def test_picamera_flag_set_by_minus_p(self):
        args, _ = camera_parser().parse_known_args(['-p'])
        self.assertTrue(args.picamera)

    def test_vimbax_flag_false_by_default(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertFalse(args.vimbax)

    def test_vimbax_flag_set_by_minus_v(self):
        args, _ = camera_parser().parse_known_args(['-v'])
        self.assertTrue(args.vimbax)

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

    def test_log_level_is_absent_unless_given(self):
        args, _ = camera_parser().parse_known_args([])
        self.assertFalse(hasattr(args, 'log_level'))

    def test_log_level_accepts_either_case(self):
        for text in ('debug', 'DEBUG', 'Debug'):
            with self.subTest(text=text):
                args, _ = camera_parser().parse_known_args(
                    ['--log-level', text])
                self.assertEqual(args.log_level, 'DEBUG')

    def test_log_level_rejects_other_values(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                camera_parser().parse_known_args(['--log-level', 'LOUD'])

    def test_version_prints_the_version_and_ends(self):
        out = io.StringIO()
        with self.assertRaises(SystemExit) as raised, \
                contextlib.redirect_stdout(out):
            camera_parser().parse_known_args(['--version'])
        self.assertEqual(raised.exception.code, 0)
        self.assertRegex(out.getvalue(), r'^QVideo \S+\n$')

    def test_options_are_not_duplicated_on_an_existing_parser(self):
        parser = ArgumentParser()
        camera_parser(parser)
        camera_parser(parser)  # a second call should not raise
        args, _ = parser.parse_known_args(['--log-level', 'info'])
        self.assertEqual(args.log_level, 'INFO')

    def test_does_not_duplicate_cameraID_on_existing_parser(self):
        parser = ArgumentParser()
        camera_parser(parser)
        camera_parser(parser)  # second call should not raise
        args, _ = parser.parse_known_args(['2'])
        self.assertEqual(args.cameraID, 2)


class TestTheWorker(unittest.TestCase):

    '''The backends whose library holds the interpreter lock open in a
    process of their own, and nothing asks for it.'''

    def test_the_harvesters_backends_use_the_worker(self):
        self.assertEqual(
            sorted(key for key, entry in BACKENDS.items() if entry.worker),
            ['basler', 'flir', 'ids', 'mv', 'vimbax'])

    def test_the_others_do_not(self):
        for key in ('viva', 'opencv', 'picamera', 'noise'):
            with self.subTest(key):
                self.assertFalse(chooser_module.uses_worker(key))

    def test_the_harvesters_backends_use_it_on_macos_and_linux(self):
        for platform in ('darwin', 'linux'):
            with self.subTest(platform), \
                    patch.object(chooser_module.sys, 'platform', platform):
                self.assertTrue(chooser_module.uses_worker('flir'))

    def test_not_on_windows_where_there_is_no_worker(self):
        with patch.object(chooser_module.sys, 'platform', 'win32'):
            self.assertFalse(chooser_module.uses_worker('flir'))

    def test_a_camera_that_uses_it_is_made_by_the_worker(self):
        proxy, cls = MagicMock(), MagicMock()
        with patch.object(chooser_module, 'uses_worker', return_value=True), \
                patch.object(chooser_module, 'camera_class',
                             return_value=cls), \
                patch('QVideo.lib.remote.QRemoteCamera',
                      return_value=proxy) as remote:
            camera = chooser_module.create_camera('flir', 2)
        self.assertIs(camera, proxy)
        cls.precheck.assert_called_once_with()
        remote.assert_called_once_with('flir', cameraID=2)

    def test_the_class_may_refuse_before_a_worker_starts(self):
        # No producer: say so here, in milliseconds, not after a process.
        refusal = QDriverError('no producer')
        cls = MagicMock()
        cls.precheck.side_effect = refusal
        errors = []
        with patch.object(chooser_module, 'uses_worker', return_value=True), \
                patch.object(chooser_module, 'camera_class',
                             return_value=cls), \
                patch('QVideo.lib.remote.QRemoteCamera') as remote:
            camera = chooser_module.create_camera('flir', 0, errors)
        self.assertIsNone(camera)
        remote.assert_not_called()
        self.assertEqual(errors, [('Flir', refusal)])

    @unittest.skipIf(sys.platform == 'win32', 'there is no worker on Windows')
    def test_the_worker_delivers_frames_through_the_chooser(self):
        # The noise camera stands in for a Harvesters backend: the chooser
        # opens it in a worker process of its own, which makes real frames.
        from QVideo.lib.remote import QRemoteCamera
        entry = BACKENDS['noise']._replace(worker=True)
        with patch.dict(BACKENDS, {'noise': entry}):
            camera = chooser_module.create_camera('noise')
        self.addCleanup(camera.close)
        self.assertIsInstance(camera, QRemoteCamera)
        self.assertTrue(camera.isOpen())
        ok, frame = camera.saferead()
        self.assertTrue(ok)
        self.assertEqual(frame.ndim, 2)

    def test_there_is_no_flag_for_it(self):
        parser = camera_parser()
        self.assertNotIn('-r', parser._option_string_actions)
        args, unknown = parser.parse_known_args(['-r'])
        self.assertIn('-r', unknown)
        self.assertFalse(hasattr(args, 'remote'))


class TestOpened(unittest.TestCase):
    '''The candidates that open, one at a time.'''

    def camera(self, is_open=True):
        camera = MagicMock()
        camera.isOpen.return_value = is_open
        return camera

    def test_only_candidates_that_open_are_yielded_in_order(self):
        made = {'flir': self.camera(False), 'opencv': self.camera(),
                'noise': self.camera()}
        errors = []
        with patch.object(chooser_module, 'create_camera',
                          side_effect=lambda key, i, errors=None:
                          made[key]):
            found = list(chooser_module._opened(
                [('flir', 0), ('opencv', 0), ('noise', 0)], errors))
        self.assertEqual(found, [('opencv', 0, made['opencv']),
                                 ('noise', 0, made['noise'])])

    def test_a_camera_that_did_not_open_is_recorded(self):
        errors = []
        with patch.object(chooser_module, 'create_camera',
                          return_value=self.camera(False)):
            list(chooser_module._opened([('flir', 0)], errors))
        self.assertEqual(errors, [('Flir', 'device failed to open')])

    def test_a_camera_that_could_not_be_made_is_skipped(self):
        with patch.object(chooser_module, 'create_camera',
                          return_value=None):
            self.assertEqual(
                list(chooser_module._opened([('flir', 0)], [])), [])

    def test_nothing_is_made_after_the_reader_stops(self):
        with patch.object(chooser_module, 'create_camera',
                          return_value=self.camera()) as create:
            found = next(chooser_module._opened(
                [('opencv', 0), ('noise', 0)], []))
        self.assertEqual(found[0], 'opencv')
        create.assert_called_once()


class TestOrder(unittest.TestCase):

    def test_backends_are_tried_in_the_order_of_the_table(self):
        with patch.object(chooser_module, '_probe', return_value=True):
            keys = [key for key, _ in chooser_module.discover(None)]
        self.assertEqual(keys, list(BACKENDS))

    def test_the_simulated_camera_is_tried_last(self):
        self.assertEqual(list(BACKENDS)[-1], 'noise')


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


class TestBackendClasses(unittest.TestCase):

    def test_camera_class_of_the_noise_backend(self):
        from QVideo.cameras.Noise import QNoiseCamera
        self.assertIs(chooser_module.camera_class('noise'), QNoiseCamera)

    def test_tree_class_of_the_noise_backend(self):
        from QVideo.cameras.Noise import QNoiseTree
        self.assertIs(chooser_module.tree_class('noise'), QNoiseTree)

    def test_an_unknown_backend_is_a_key_error(self):
        with self.assertRaises(KeyError):
            chooser_module.camera_class('nothing')


class TestOpenCameraAndMakeTree(unittest.TestCase):
    '''Opening a camera builds no widget; the tree is a second step.'''

    def test_open_camera_returns_the_key_and_an_open_camera(self):
        with patch('sys.argv', ['prog']):
            key, camera = open_camera()
        self.assertEqual(key, 'noise')
        self.assertTrue(camera.isOpen())
        camera.close()

    def test_open_camera_works_in_a_thread_without_a_widget(self):
        from QVideo.lib import QCamera
        result = []
        with patch('sys.argv', ['prog']):
            thread = threading.Thread(
                target=lambda: result.append(open_camera()))
            thread.start()
            thread.join(10)
        key, camera = result[0]
        self.assertIsInstance(camera, QCamera)
        camera.close()

    def test_make_tree_builds_the_tree_of_the_backend(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog']):
            key, camera = open_camera()
        tree = make_tree(key, camera)
        self.assertIsInstance(tree, QNoiseTree)
        self.assertIs(tree.camera, camera)
        tree.close()


class TestChooseCameraOpenCV(unittest.TestCase):

    def test_opencv_flag_returns_opencv_camera(self):
        from QVideo.cameras.OpenCV import QOpenCVTree
        device = make_mock_cv2_device()
        with patch('sys.argv', ['prog', '-c']):
            with patch('cv2.VideoCapture', return_value=device):
                with patch('QVideo.cameras.OpenCV._camera.configure'):
                    camera = choose_camera()
        self.assertIsInstance(camera, QOpenCVTree)
        camera.close()

    def test_opencv_flag_forwards_cameraID(self):
        device = make_mock_cv2_device()
        with patch('sys.argv', ['prog', '-c', '2']):
            with patch('cv2.VideoCapture', return_value=device) as mock_cap:
                with patch('QVideo.cameras.OpenCV._camera.configure'):
                    camera = choose_camera()
        args, _ = mock_cap.call_args
        self.assertEqual(args[0], 2)
        camera.close()

    def test_opencv_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-c']):
            with patch('QVideo.cameras.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.OpenCV': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()


class TestChooseCameraFallback(unittest.TestCase):

    '''A backend that fails to open falls back to the noise camera.

    The backends are mocked as modules in the program: with the worker they
    would open a process of their own, and a camera on this machine.
    '''

    def setUp(self):
        patcher = patch.object(chooser_module, 'uses_worker',
                               return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_driver_error_reason_is_logged_before_fallback(self):
        from QVideo.cameras.Noise import QNoiseTree
        from QVideo.lib.errors import QDriverError
        reason = 'GENICAM_GENTL64_PATH is not set'
        fake = MagicMock(side_effect=QDriverError(reason))
        module = MagicMock(QFlirCamera=fake)
        with patch('sys.argv', ['prog', '-f']):
            with patch('QVideo.cameras.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.Flir': module}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        self.assertIn(reason, mock_logger.warning.call_args[0][0])
        camera.close()

    def test_flir_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-f']):
            with patch('QVideo.cameras.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.Flir': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()

    def test_basler_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-b']):
            with patch('QVideo.cameras.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.Basler': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()

    def test_ids_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-i']):
            with patch('QVideo.cameras.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.IDS': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()

    def test_mv_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-m']):
            with patch('QVideo.cameras.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.MV': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()

    def test_picamera_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-p']):
            with patch('QVideo.cameras.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.Picamera': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()

    def test_vimbax_import_failure_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        with patch('sys.argv', ['prog', '-v']):
            with patch('QVideo.cameras.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.Vimbax': None}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        mock_logger.warning.assert_called_once()
        camera.close()

    def test_runtime_error_falls_back_to_noise(self):
        from QVideo.cameras.Noise import QNoiseTree
        mock_module = MagicMock()
        mock_module.QOpenCVCamera.side_effect = TypeError('no producer')
        with patch('sys.argv', ['prog', '-c']):
            with patch('QVideo.cameras.chooser.logger') as mock_logger:
                with patch.dict('sys.modules',
                                {'QVideo.cameras.OpenCV': mock_module}):
                    camera = choose_camera()
        self.assertIsInstance(camera, QNoiseTree)
        messages = [call.args[0]
                    for call in mock_logger.warning.call_args_list]
        self.assertTrue(any('No camera could be opened' in m
                            for m in messages), messages)
        camera.close()


if __name__ == '__main__':
    unittest.main()
