'''Unit tests for interactive/camera.py and cameras/registry.py.'''
import asyncio
import contextlib
import importlib
import io
import logging
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from qtpy import QtWidgets

import QVideo.interactive.camera as camera_module
from QVideo.cameras.registry import _BACKENDS, _discover, _probe
from QVideo.interactive.camera import Camera, _CameraProxy

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _jupyter():
    '''The notebook front end; it needs ipywidgets.'''
    return importlib.import_module('QVideo.interactive.widgets')

_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


def make_mock_noise_camera(open_ok=True, read_ok=True):
    cam = MagicMock()
    cam.isOpen.return_value = open_ok
    cam.saferead.return_value = (read_ok, _FRAME.copy() if read_ok else None)
    return cam


class TestBackendsRegistry(unittest.TestCase):

    def test_backends_is_dict(self):
        self.assertIsInstance(_BACKENDS, dict)

    def test_required_backends_present(self):
        for key in ('basler', 'flir', 'ids', 'mv', 'vimbax',
                    'picamera', 'opencv', 'noise'):
            with self.subTest(key=key):
                self.assertIn(key, _BACKENDS)

    def test_each_entry_names_its_module_classes_and_label(self):
        for key, entry in _BACKENDS.items():
            with self.subTest(key=key):
                self.assertTrue(all(entry[:4]))

    def test_the_flag_and_help_come_together(self):
        for key, entry in _BACKENDS.items():
            with self.subTest(key=key):
                self.assertEqual(bool(entry.flag), bool(entry.help))

    def test_noise_backend_points_to_correct_module(self):
        self.assertEqual(_BACKENDS['noise'].module, 'QVideo.cameras.Noise')

    def test_opencv_backend_points_to_correct_module(self):
        self.assertEqual(_BACKENDS['opencv'].module, 'QVideo.cameras.OpenCV')


class TestProbe(unittest.TestCase):

    def test_returns_true_for_importable_module(self):
        self.assertTrue(_probe('noise'))

    def test_returns_false_when_module_blocked(self):
        with patch.dict('sys.modules', {'QVideo.cameras.Basler': None}):
            self.assertFalse(_probe('basler'))


class TestDiscover(unittest.TestCase):

    def test_returns_noise_when_no_model_and_others_blocked(self):
        blocked = {k: None for k in _BACKENDS if k != 'noise'}
        with patch.dict('sys.modules', {_BACKENDS[k].module: None
                                        for k in blocked}):
            result = _discover(None, 0)
        keys = [k for k, _ in result]
        self.assertIn('noise', keys)

    def test_model_none_returns_list_of_tuples(self):
        result = _discover(None, 0)
        self.assertIsInstance(result, list)
        for item in result:
            self.assertEqual(len(item), 2)

    def test_model_noise_returns_noise_entry(self):
        result = _discover('Noise', 0)
        self.assertEqual(result, [('noise', 0)])

    def test_model_opencv_returns_opencv_entry(self):
        result = _discover('OpenCV', 0)
        self.assertEqual(result, [('opencv', 0)])

    def test_model_case_insensitive(self):
        self.assertEqual(_discover('NOISE', 0), _discover('noise', 0))
        self.assertEqual(_discover('OpenCV', 0), _discover('opencv', 0))

    def test_unknown_model_raises_value_error(self):
        with self.assertRaises(ValueError):
            _discover('Unknown', 0)

    def test_returns_empty_when_model_module_blocked(self):
        with patch.dict('sys.modules', {'QVideo.cameras.Basler': None}):
            result = _discover('basler', 0)
        self.assertEqual(result, [])

    def test_camera_id_preserved_in_result(self):
        result = _discover('noise', 3)
        self.assertEqual(result, [('noise', 3)])


class TestCameraProxy(unittest.TestCase):

    def _make_proxy(self, open_ok=True, read_ok=True):
        cam = make_mock_noise_camera(open_ok=open_ok, read_ok=read_ok)
        with patch('QVideo.interactive.camera._open', return_value=cam):
            proxy = Camera('noise')
        return proxy, cam

    def test_read_returns_ndarray(self):
        proxy, _ = self._make_proxy()
        with patch('QVideo.interactive.camera._open',
                   return_value=make_mock_noise_camera()):
            frame = proxy.read()
        self.assertIsInstance(frame, np.ndarray)

    def test_read_raises_on_failure(self):
        proxy, _ = self._make_proxy(read_ok=False)
        with patch('QVideo.interactive.camera._open',
                   return_value=make_mock_noise_camera(read_ok=False)):
            with self.assertRaises(RuntimeError):
                proxy.read()

    def test_getattr_forwards_to_camera(self):
        proxy, cam = self._make_proxy()
        cam.fps = 30.
        with patch('QVideo.interactive.camera._open', return_value=cam):
            result = proxy.fps
        self.assertEqual(result, 30.)

    def test_setattr_forwards_to_camera(self):
        proxy, cam = self._make_proxy()
        with patch('QVideo.interactive.camera._open', return_value=cam):
            proxy.fps = 60.
        cam.__setattr__('fps', 60.)  # verify delegation happened
        self.assertEqual(cam.fps, 60.)

    def test_repr_shows_backend_label(self):
        proxy, cam = self._make_proxy()
        with patch('QVideo.interactive.camera._open', return_value=cam):
            proxy._ensure_open()
        self.assertIn('Noise', repr(proxy))

    def test_ensure_open_skips_failed_backends(self):
        fail_cam = make_mock_noise_camera(open_ok=False)
        good_cam = make_mock_noise_camera(open_ok=True)
        proxy = _CameraProxy([('basler', 0), ('noise', 0)])
        side_effects = [fail_cam, good_cam]
        with patch('QVideo.interactive.camera._open', side_effect=side_effects):
            proxy._ensure_open()
        self.assertEqual(
            object.__getattribute__(proxy, '_selected_key'), 'noise'
        )

    def test_ensure_open_raises_when_all_fail(self):
        fail_cam = make_mock_noise_camera(open_ok=False)
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.interactive.camera._open', return_value=fail_cam):
            with self.assertRaises(RuntimeError):
                proxy._ensure_open()


class TestCameraFilters(unittest.TestCase):

    def _make_proxy(self, frames=None):
        cam = make_mock_noise_camera()
        if frames is not None:
            cam.saferead.side_effect = [(True, f) for f in frames]
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.interactive.camera._open', return_value=cam):
            proxy._ensure_open()
        return proxy, cam

    def test_there_are_no_filters_at_first(self):
        proxy, _ = self._make_proxy()
        self.assertEqual(proxy.filters, [])

    def test_unfiltered_frames_are_the_cameras_frames(self):
        proxy, _ = self._make_proxy()
        np.testing.assert_array_equal(proxy.read(), _FRAME)

    def test_filters_are_applied_in_order(self):
        proxy, _ = self._make_proxy()
        proxy.filters = [lambda f: f + 1, lambda f: f * 3]
        self.assertTrue((proxy.read() == 3).all())

    def test_filters_are_not_forwarded_to_the_camera(self):
        proxy, cam = self._make_proxy()
        proxy.filters = [lambda f: f]
        self.assertNotIsInstance(cam.filters, list)

    def test_the_list_may_be_changed_in_place(self):
        proxy, _ = self._make_proxy()
        proxy.filters.append(lambda f: f + 2)
        self.assertTrue((proxy.read() == 2).all())

    def test_assigning_a_list_copies_it(self):
        proxy, _ = self._make_proxy()
        filters = [lambda f: f]
        proxy.filters = filters
        proxy.filters.append(lambda f: f)
        self.assertEqual(len(filters), 1)

    def test_an_empty_list_returns_raw_frames(self):
        proxy, _ = self._make_proxy()
        proxy.filters = [lambda f: f + 1]
        proxy.filters = []
        np.testing.assert_array_equal(proxy.read(), _FRAME)

    def test_a_filter_that_raises_is_reported_and_removed(self):
        def broken(frame):
            raise ValueError('oops')

        proxy, _ = self._make_proxy()
        good = lambda f: f + 1
        proxy.filters = [broken, good]
        with self.assertLogs('QVideo.interactive.camera', 'WARNING') as logs:
            frame = proxy.read()
        self.assertIn('broken', logs.output[0])
        self.assertIn('oops', logs.output[0])
        self.assertEqual(proxy.filters, [good])
        self.assertTrue((frame == 1).all())

    def test_a_filter_without_a_result_asks_for_another_frame(self):
        frames = [np.full((2, 2), n, np.uint8) for n in range(3)]
        seen = []

        def third(frame):
            seen.append(int(frame[0, 0]))
            return frame if len(seen) == 3 else None

        proxy, cam = self._make_proxy(frames)
        proxy.filters = [third]
        self.assertEqual(int(proxy.read()[0, 0]), 2)
        self.assertEqual(seen, [0, 1, 2])
        self.assertEqual(cam.saferead.call_count, 3)

    def test_a_failed_read_still_raises(self):
        proxy, cam = self._make_proxy()
        cam.saferead.return_value = (False, None)
        proxy.filters = [lambda f: f]
        with self.assertRaises(RuntimeError):
            proxy.read()

    def test_the_filters_of_the_library_work(self):
        from QVideo.filters import InvertFilter
        proxy, _ = self._make_proxy()
        proxy.filters = [InvertFilter()]
        self.assertTrue((proxy.read() == 255).all())

    def test_live_view_shows_the_filtered_frames(self):
        proxy, cam = self._make_proxy()
        proxy.filters = [lambda f: f + 7]
        shown = []
        fake = MagicMock(side_effect=lambda read, fps: shown.append(read()))
        with patch.object(_jupyter(), 'live_view', fake):
            proxy.live_view()
        self.assertTrue((shown[0] == 7).all())


class TestApplication(unittest.TestCase):

    def test_the_application_that_a_camera_makes_stays_alive(self):
        # Needs a process of its own: this one already has an application.
        import os
        import subprocess
        import sys
        code = ('from qtpy.QtWidgets import QApplication\n'
                'from QVideo import Camera\n'
                "Camera('Noise').read()\n"
                'print(QApplication.instance() is not None)')
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        result = subprocess.run([sys.executable, '-c', code], env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.stdout.split()[-1], 'True', result.stderr)


class TestOpenErrors(unittest.TestCase):

    def test_open_records_exception(self):
        errors = []
        boom = RuntimeError('GENICAM_GENTL64_PATH is not set')
        with patch('importlib.import_module', side_effect=boom):
            self.assertIsNone(camera_module._open('flir', 0, errors))
        self.assertEqual(errors, [('Flir', boom)])

    def test_open_logs_where_the_failure_was(self):
        boom = RuntimeError('Feature not present')
        with patch('importlib.import_module', side_effect=boom):
            with self.assertLogs('QVideo.interactive.camera', 'DEBUG') as logs:
                camera_module._open('flir', 0, [])
        record = [r for r in logs.records if r.levelname == 'DEBUG'][0]
        self.assertIn('Flir', record.getMessage())
        self.assertIs(record.exc_info[1], boom)

    def test_probing_is_quiet_unless_debug_logging_is_on(self):
        logger = logging.getLogger('QVideo')
        for level, shown in ((logging.WARNING, False), (logging.DEBUG, True)):
            with self.subTest(level=level):
                saved = logger.level
                logger.setLevel(level)
                try:
                    with camera_module._quiet():
                        self.assertEqual(
                            logger.isEnabledFor(logging.DEBUG), shown)
                        self.assertEqual(logger.level, level if shown
                                         else logging.ERROR)
                    self.assertEqual(logger.level, level)
                finally:
                    logger.setLevel(saved)

    def test_ensure_open_error_lists_reason_per_backend(self):
        proxy = _CameraProxy([('flir', 0), ('basler', 0)])

        def fake_open(key, camera_id, errors):
            errors.append((_BACKENDS[key].label, RuntimeError(f'why {key}')))
        with patch('QVideo.interactive.camera._open', side_effect=fake_open):
            with self.assertRaises(RuntimeError) as ctx:
                proxy._ensure_open()
        message = str(ctx.exception)
        self.assertIn('Flir: why flir', message)
        self.assertIn('Basler: why basler', message)

    def test_noise_fallback_warning_includes_reasons(self):
        proxy = _CameraProxy([('flir', 0), ('noise', 0)])
        noise = make_mock_noise_camera()

        def fake_open(key, camera_id, errors):
            if key == 'flir':
                errors.append(('Flir', RuntimeError('no producer')))
                return None
            return noise
        with patch('QVideo.interactive.camera._open', side_effect=fake_open):
            with self.assertLogs('QVideo.interactive.camera', 'WARNING') as logs:
                proxy._ensure_open()
        self.assertIn('Flir: no producer', logs.output[0])

    def test_closed_camera_is_reported(self):
        proxy = _CameraProxy([('flir', 0)])
        with patch('QVideo.interactive.camera._open',
                   return_value=make_mock_noise_camera(open_ok=False)):
            with self.assertRaisesRegex(RuntimeError, 'Flir: device failed'):
                proxy._ensure_open()

    def test_explicit_model_reports_import_failure(self):
        with patch('QVideo.cameras.registry._probe', return_value=False), \
             patch('importlib.import_module',
                   side_effect=ImportError('pip install genicam harvesters')):
            with self.assertRaisesRegex(RuntimeError, 'pip install genicam'):
                Camera('flir')


class TestCameraFactory(unittest.TestCase):

    def test_returns_camera_proxy(self):
        cam = make_mock_noise_camera()
        with patch('QVideo.interactive.camera._open', return_value=cam):
            result = Camera('noise')
        self.assertIsInstance(result, _CameraProxy)

    def test_no_model_returns_proxy(self):
        cam = make_mock_noise_camera()
        blocked = {_BACKENDS[k].module: None
                   for k in _BACKENDS if k != 'noise'}
        with patch.dict('sys.modules', blocked):
            with patch('QVideo.interactive.camera._open', return_value=cam):
                result = Camera()
        self.assertIsInstance(result, _CameraProxy)

    def test_unknown_model_raises_value_error(self):
        with self.assertRaises(ValueError):
            Camera('Unknown')

    def test_unavailable_model_raises_runtime_error(self):
        with patch.dict('sys.modules', {'QVideo.cameras.Basler': None}):
            with self.assertRaises(RuntimeError):
                Camera('basler')

    def test_camera_id_forwarded(self):
        cam = make_mock_noise_camera()
        with patch('QVideo.interactive.camera._open', return_value=cam) as mock_open:
            proxy = Camera('noise', cameraID=2)
            proxy._ensure_open()
        mock_open.assert_called_once_with('noise', 2, [])

    def test_top_level_export(self):
        import QVideo
        self.assertIs(QVideo.Camera, Camera)

    def test_interactive_export(self):
        from QVideo.interactive import Camera as InteractiveCamera
        self.assertIs(InteractiveCamera, Camera)


class TestLiveView(unittest.TestCase):

    def _make_proxy(self):
        cam = make_mock_noise_camera()
        with patch('QVideo.interactive.camera._open', return_value=cam):
            proxy = Camera('noise')
        return proxy, cam

    def test_live_view_returns_live_view_handle(self):
        from QVideo.interactive.widgets import LiveView

        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        proxy, cam = self._make_proxy()
        with patch('QVideo.interactive.camera._open', return_value=cam):
            with patch('ipywidgets.Image'):
                with patch('QVideo.interactive.widgets._display'):
                    with patch('asyncio.ensure_future',
                               side_effect=_close_and_return):
                        lv = proxy.live_view()
        self.assertIsInstance(lv, LiveView)

    def test_live_view_says_why_it_stopped(self):
        import asyncio
        proxy, cam = self._make_proxy()
        loops = []

        def _keep(coro):
            loops.append(coro)
            return MagicMock()

        with patch('QVideo.interactive.camera._open', return_value=cam):
            with patch('ipywidgets.Image'):
                with patch('QVideo.interactive.widgets._display'):
                    with patch('asyncio.ensure_future', side_effect=_keep):
                        proxy.live_view()
        cam.saferead.return_value = (False, None)  # the camera went away
        with self.assertLogs('QVideo.interactive.widgets', 'WARNING') as logs:
            asyncio.run(asyncio.wait_for(loops[0], timeout=5))
        self.assertIn('Camera read failed', logs.output[0])

    def test_live_view_stop_cancels_task(self):
        from QVideo.interactive.widgets import LiveView
        mock_task = MagicMock()
        lv = LiveView(mock_task)
        lv.stop()
        mock_task.cancel.assert_called_once()

    def test_live_view_schedules_async_loop(self):
        proxy, cam = self._make_proxy()

        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        with patch('QVideo.interactive.camera._open', return_value=cam):
            with patch('ipywidgets.Image'):
                with patch('QVideo.interactive.widgets._display'):
                    with patch('asyncio.ensure_future',
                               side_effect=_close_and_return) as mock_future:
                        proxy.live_view()
        mock_future.assert_called_once()

    def test_live_view_stores_handle_on_proxy(self):
        from QVideo.interactive.widgets import LiveView

        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        proxy, cam = self._make_proxy()
        with patch('QVideo.interactive.camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('QVideo.interactive.widgets._display'), \
             patch('asyncio.ensure_future', side_effect=_close_and_return):
            proxy.live_view()
        lv = object.__getattribute__(proxy, '_live_view')
        self.assertIsInstance(lv, LiveView)

    def test_stop_live_view_cancels_task(self):
        mock_task = MagicMock()

        def _close_and_return(coro):
            coro.close()
            return mock_task

        proxy, cam = self._make_proxy()
        with patch('QVideo.interactive.camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('QVideo.interactive.widgets._display'), \
             patch('asyncio.ensure_future', side_effect=_close_and_return):
            proxy.live_view()
        proxy.stop_live_view()
        mock_task.cancel.assert_called_once()

    def test_stop_live_view_clears_handle(self):
        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        proxy, cam = self._make_proxy()
        with patch('QVideo.interactive.camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('QVideo.interactive.widgets._display'), \
             patch('asyncio.ensure_future', side_effect=_close_and_return):
            proxy.live_view()
        proxy.stop_live_view()
        self.assertIsNone(object.__getattribute__(proxy, '_live_view'))

    def test_stop_live_view_safe_when_no_feed(self):
        proxy, _ = self._make_proxy()
        proxy.stop_live_view()  # should not raise

    def test_live_view_raises_without_ipywidgets(self):
        proxy, _ = self._make_proxy()
        with patch.dict('sys.modules', {'QVideo.interactive.widgets': None}):
            with self.assertRaisesRegex(ImportError,
                                        r'ipywidgets is required for '
                                        r'live_view\(\)'):
                proxy.live_view()

    def test_controls_raise_without_ipywidgets(self):
        proxy, _ = self._make_proxy()
        with patch.dict('sys.modules', {'QVideo.interactive.widgets': None}):
            with self.assertRaisesRegex(ImportError,
                                        r'ipywidgets is required for '
                                        r'camera\.controls\(\)'):
                proxy.controls()

    def test_controls_are_made_for_the_camera(self):
        proxy, cam = self._make_proxy()
        notebook = MagicMock()
        with patch.object(camera_module, '_notebook', return_value=notebook), \
             patch.object(camera_module, '_open', return_value=cam):
            controls = proxy.controls()
        notebook.CameraControls.assert_called_once_with(cam)
        self.assertIs(controls, notebook.CameraControls.return_value)

    def test_live_view_encodes_rgb_as_bgr(self):
        import cv2
        proxy, cam = self._make_proxy()
        rgb_frame = np.zeros((4, 4, 3), dtype=np.uint8)
        rgb_frame[0, 0] = [255, 0, 0]  # red pixel in RGB
        cam.saferead.return_value = (True, rgb_frame)

        encoded = []

        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        original_imencode = cv2.imencode

        def capture_imencode(ext, f):
            encoded.append(f.copy())
            return original_imencode(ext, f)

        with patch('QVideo.interactive.camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('QVideo.interactive.widgets._display'), \
             patch('asyncio.ensure_future', side_effect=_close_and_return), \
             patch('cv2.imencode', side_effect=capture_imencode):
            proxy.live_view()

        self.assertTrue(len(encoded) > 0)
        np.testing.assert_array_equal(encoded[0][0, 0], [0, 0, 255])  # BGR

    def test_live_view_grayscale_not_swapped(self):
        import cv2
        proxy, cam = self._make_proxy()
        gray_frame = np.zeros((4, 4), dtype=np.uint8)
        gray_frame[0, 0] = 128
        cam.saferead.return_value = (True, gray_frame)

        encoded = []

        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        original_imencode = cv2.imencode

        def capture_imencode(ext, f):
            encoded.append(f.copy())
            return original_imencode(ext, f)

        with patch('QVideo.interactive.camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('QVideo.interactive.widgets._display'), \
             patch('asyncio.ensure_future', side_effect=_close_and_return), \
             patch('cv2.imencode', side_effect=capture_imencode):
            proxy.live_view()

        self.assertTrue(len(encoded) > 0)
        self.assertEqual(encoded[0][0, 0], 128)


class TestJupyterChooser(unittest.TestCase):

    _WORKING_TWO = [('opencv', 0), ('flir', 0)]
    _WORKING_ONE = [('noise', 0)]
    _OPTIONS = [('OpenCV', ('opencv', 0)), ('Noise', ('noise', 0))]

    def _run(self, coro):
        return asyncio.run(coro)

    def _make_widget_mocks(self):
        '''Return (mock_dropdown, mock_button, click_callbacks list).'''
        mock_dropdown = MagicMock()
        mock_dropdown.value = ('opencv', 0)
        mock_button = MagicMock()
        callbacks = []
        mock_button.on_click.side_effect = lambda cb: callbacks.append(cb)
        return mock_dropdown, mock_button, callbacks

    def _patched_chooser(self, working, mock_dropdown, mock_button):
        return (
            patch('ipywidgets.Dropdown', return_value=mock_dropdown),
            patch('ipywidgets.Button', return_value=mock_button),
            patch('ipywidgets.HBox', return_value=MagicMock()),
            patch('ipywidgets.Layout', return_value=MagicMock()),
            patch('QVideo.interactive.widgets._display'),
        )

    def test_noise_alone_says_that_no_hardware_was_found(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = self._run(camera_module._choose(self._WORKING_ONE))
        self.assertEqual(result, ('noise', 0))
        self.assertIn('No camera hardware found', out.getvalue())

    def test_one_real_camera_is_used_without_asking(self):
        working = [('opencv', 0), ('noise', 0)]
        with patch.object(camera_module, '_report') as mock_report, \
                patch.object(camera_module, '_notebook') as notebook:
            result = self._run(camera_module._choose(working))
        notebook.assert_not_called()
        mock_report.assert_called_once_with([('opencv', 0)])
        self.assertEqual(result, ('opencv', 0))

    def test_the_real_camera_wins_wherever_noise_is_listed(self):
        working = [('noise', 0), ('opencv', 0)]
        with patch.object(camera_module, '_report'):
            result = self._run(camera_module._choose(working))
        self.assertEqual(result, ('opencv', 0))

    def test_the_prompt_says_how_to_get_past_a_widget_that_is_not_drawn(self):
        mock_dropdown, mock_button, callbacks = self._make_widget_mocks()
        out = io.StringIO()

        async def run():
            async def fire():
                await asyncio.sleep(0)
                for cb in callbacks:
                    cb(None)
            asyncio.ensure_future(fire())
            with patch('ipywidgets.Dropdown', return_value=mock_dropdown), \
                 patch('ipywidgets.Button', return_value=mock_button), \
                 patch('ipywidgets.HBox', return_value=MagicMock()), \
                 patch('ipywidgets.Layout', return_value=MagicMock()), \
                 patch('QVideo.interactive.widgets._display'), \
                 contextlib.redirect_stdout(out):
                await camera_module._choose(self._WORKING_TWO)

        self._run(run())
        text = out.getvalue()
        self.assertIn('press Open', text)
        self.assertIn('HBox(...)', text)
        self.assertIn("Camera('OpenCV')", text)

    def test_the_dropdown_labels_the_cameras_by_backend(self):
        mock_dropdown, mock_button, callbacks = self._make_widget_mocks()

        async def run():
            async def fire():
                await asyncio.sleep(0)
                for cb in callbacks:
                    cb(None)
            asyncio.ensure_future(fire())
            with patch('ipywidgets.Dropdown',
                       return_value=mock_dropdown) as dropdown, \
                 patch('ipywidgets.Button', return_value=mock_button), \
                 patch('ipywidgets.HBox', return_value=MagicMock()), \
                 patch('ipywidgets.Layout', return_value=MagicMock()), \
                 patch('QVideo.interactive.widgets._display'):
                await camera_module._choose(self._WORKING_TWO)
            return dropdown

        dropdown = self._run(run())
        self.assertEqual(dropdown.call_args.kwargs['options'],
                         [('OpenCV', ('opencv', 0)), ('Flir', ('flir', 0))])

    def test_returns_selected_camera(self):
        mock_dropdown, mock_button, callbacks = self._make_widget_mocks()
        mock_dropdown.value = ('noise', 0)

        async def run():
            async def fire():
                await asyncio.sleep(0)
                for cb in callbacks:
                    cb(None)
            asyncio.ensure_future(fire())
            with patch('ipywidgets.Dropdown', return_value=mock_dropdown), \
                 patch('ipywidgets.Button', return_value=mock_button), \
                 patch('ipywidgets.HBox', return_value=MagicMock()), \
                 patch('ipywidgets.Layout', return_value=MagicMock()), \
                 patch('QVideo.interactive.widgets._display'):
                return await _jupyter().choose(self._OPTIONS)

        result = self._run(run())
        self.assertEqual(result, ('noise', 0))

    def test_displays_hbox_with_dropdown_and_button(self):
        mock_dropdown, mock_button, callbacks = self._make_widget_mocks()

        async def run():
            async def fire():
                await asyncio.sleep(0)
                for cb in callbacks:
                    cb(None)
            asyncio.ensure_future(fire())
            with patch('ipywidgets.Dropdown', return_value=mock_dropdown), \
                 patch('ipywidgets.Button', return_value=mock_button), \
                 patch('ipywidgets.HBox', return_value=MagicMock()) as mock_hbox_cls, \
                 patch('ipywidgets.Layout', return_value=MagicMock()), \
                 patch('QVideo.interactive.widgets._display') as mock_display:
                await _jupyter().choose(self._OPTIONS)
                mock_hbox_cls.assert_called_once_with([mock_dropdown, mock_button])
                mock_display.assert_called_once()

        self._run(run())

    def test_double_click_ignored(self):
        mock_dropdown, mock_button, callbacks = self._make_widget_mocks()
        mock_dropdown.value = ('opencv', 0)

        async def run():
            async def fire_twice():
                await asyncio.sleep(0)
                for cb in callbacks:
                    cb(None)
                    cb(None)
            asyncio.ensure_future(fire_twice())
            with patch('ipywidgets.Dropdown', return_value=mock_dropdown), \
                 patch('ipywidgets.Button', return_value=mock_button), \
                 patch('ipywidgets.HBox', return_value=MagicMock()), \
                 patch('ipywidgets.Layout', return_value=MagicMock()), \
                 patch('QVideo.interactive.widgets._display'):
                return await _jupyter().choose(self._OPTIONS)

        result = self._run(run())
        self.assertEqual(result, ('opencv', 0))

    def test_click_disables_dropdown_and_button(self):
        mock_dropdown, mock_button, callbacks = self._make_widget_mocks()

        async def run():
            async def fire():
                await asyncio.sleep(0)
                for cb in callbacks:
                    cb(None)
            asyncio.ensure_future(fire())
            with patch('ipywidgets.Dropdown', return_value=mock_dropdown), \
                 patch('ipywidgets.Button', return_value=mock_button), \
                 patch('ipywidgets.HBox', return_value=MagicMock()), \
                 patch('ipywidgets.Layout', return_value=MagicMock()), \
                 patch('QVideo.interactive.widgets._display'):
                await _jupyter().choose(self._OPTIONS)

        self._run(run())
        self.assertTrue(mock_dropdown.disabled)
        self.assertTrue(mock_button.disabled)
        self.assertEqual(mock_button.button_style, '')

    def test_without_ipywidgets_the_cameras_are_reported(self):
        with patch.dict('sys.modules', {'QVideo.interactive.widgets': None}), \
                patch.object(camera_module, '_report') as mock_report:
            result = self._run(camera_module._choose(self._WORKING_TWO))
        mock_report.assert_called_once_with(self._WORKING_TWO)
        self.assertEqual(result, ('opencv', 0))


class TestHelpers(unittest.TestCase):
    '''The small functions that the factory is built from.'''

    def test_a_qapplication_is_made_if_there_is_none(self):
        fake = MagicMock()
        fake.instance.return_value = None
        with patch('qtpy.QtWidgets.QApplication', fake):
            camera_module._ensure_qapp()
        fake.assert_called_once_with([])

    def test_an_existing_qapplication_is_kept(self):
        fake = MagicMock()
        with patch('qtpy.QtWidgets.QApplication', fake):
            camera_module._ensure_qapp()
        fake.assert_not_called()

    def test_an_importable_backend_has_no_reason(self):
        self.assertEqual(camera_module._unavailable('noise'), '')

    def test_an_unimportable_backend_gives_the_reason(self):
        with patch.dict('sys.modules', {'QVideo.cameras.Basler': None}):
            reason = camera_module._unavailable('basler')
        self.assertTrue(reason.startswith(':\n'))

    def test_only_cameras_that_open_are_working(self):
        good, bad = make_mock_noise_camera(), make_mock_noise_camera(False)
        cameras = {'noise': good, 'opencv': bad, 'flir': None}
        with patch.object(camera_module, '_open',
                          side_effect=lambda key, i: cameras[key]):
            working = camera_module._working_candidates(
                [('noise', 0), ('opencv', 0), ('flir', 0)])
        self.assertEqual(working, [('noise', 0)])
        good.close.assert_called_once_with()
        bad.close.assert_not_called()

    def test_available_cameras_name_each_working_device(self):
        names = {0: 'Front', 1: 'Back'}
        with patch.object(camera_module, '_discover',
                          return_value=[('opencv', 0), ('noise', 0)]), \
                patch.object(camera_module, '_names',
                             side_effect=lambda k: names if k == 'opencv'
                             else {}), \
                patch.object(camera_module, '_working_candidates',
                             side_effect=lambda c: [x for x in c
                                                    if x != ('opencv', 1)]):
            found = camera_module.available_cameras()
        self.assertEqual(found, [('OpenCV', 0, 'Front'),
                                 ('Noise', 0, 'Noise')])

    def test_available_cameras_are_exported(self):
        import QVideo
        self.assertIs(QVideo.available_cameras,
                      camera_module.available_cameras)

    def test_one_camera_is_reported_by_name(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            camera_module._report([('noise', 0)])
        self.assertEqual(out.getvalue(),
                         f"Camera: {_BACKENDS['noise'].label}\n")

    def test_several_cameras_say_how_to_pick_another(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            camera_module._report([('opencv', 0), ('noise', 0)])
        text = out.getvalue()
        self.assertIn(f"Using {_BACKENDS['opencv'].label}", text)
        self.assertIn(f"Camera('{_BACKENDS['noise'].label}')", text)

    def test_awaiting_the_proxy_selects_a_camera(self):
        proxy = _CameraProxy([('noise', 0)])

        async def select():
            return proxy

        async def wait():
            return await proxy

        with patch.object(_CameraProxy, '_select', lambda self: select()):
            self.assertIs(asyncio.run(wait()), proxy)


class TestAwait(unittest.TestCase):
    '''``await Camera()`` chooses a camera, but only in an IPython session.'''

    CANDIDATES = [('opencv', 0), ('noise', 0)]

    def select(self, proxy, in_ipython, working, choose=None):
        cam = make_mock_noise_camera()
        patches = [
            patch.object(camera_module, '_in_ipython',
                         return_value=in_ipython),
            patch.object(camera_module, '_working_candidates',
                         return_value=working),
            patch('QVideo.interactive.camera._open', return_value=cam)]
        if choose is not None:
            patches.append(patch.object(camera_module, '_choose', choose))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return asyncio.run(proxy._select())

    def test_outside_ipython_the_first_camera_is_opened(self):
        proxy = _CameraProxy(list(self.CANDIDATES))
        self.assertIs(self.select(proxy, False, []), proxy)
        self.assertEqual(object.__getattribute__(proxy, '_selected_key'),
                         'opencv')

    def test_the_chosen_camera_becomes_the_only_candidate(self):
        proxy = _CameraProxy(list(self.CANDIDATES))

        async def choose(working):
            return ('noise', 0)

        self.select(proxy, True, self.CANDIDATES, choose)
        self.assertEqual(object.__getattribute__(proxy, '_candidates'),
                         [('noise', 0)])
        self.assertEqual(object.__getattribute__(proxy, '_selected_key'),
                         'noise')

    def test_when_nothing_works_the_candidates_are_left_alone(self):
        proxy = _CameraProxy(list(self.CANDIDATES))
        self.select(proxy, True, [])
        self.assertEqual(object.__getattribute__(proxy, '_candidates'),
                         self.CANDIDATES)

    def test_a_single_candidate_is_not_probed(self):
        proxy = _CameraProxy([('noise', 0)])
        self.select(proxy, True, [])
        camera_module._working_candidates.assert_not_called()


class TestInIPython(unittest.TestCase):

    def test_false_outside_ipython(self):
        with patch('IPython.get_ipython', return_value=None):
            self.assertFalse(camera_module._in_ipython())

    def test_true_in_an_ipython_session(self):
        with patch('IPython.get_ipython', return_value=object()):
            self.assertTrue(camera_module._in_ipython())

    def test_false_when_ipython_is_not_installed(self):
        with patch.dict('sys.modules', {'IPython': None}):
            self.assertFalse(camera_module._in_ipython())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
