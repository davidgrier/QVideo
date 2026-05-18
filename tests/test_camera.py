'''Unit tests for lib/_camera.py.'''
import asyncio
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from qtpy import QtWidgets

import QVideo.lib._camera as camera_module
from QVideo.lib._camera import Camera, _BACKENDS, _CameraProxy, _discover, _probe

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

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

    def test_each_entry_has_four_fields(self):
        for key, entry in _BACKENDS.items():
            with self.subTest(key=key):
                self.assertEqual(len(entry), 4)

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
        with patch('QVideo.lib._camera._open', return_value=cam):
            proxy = Camera('noise')
        return proxy, cam

    def test_read_returns_ndarray(self):
        proxy, _ = self._make_proxy()
        with patch('QVideo.lib._camera._open',
                   return_value=make_mock_noise_camera()):
            frame = proxy.read()
        self.assertIsInstance(frame, np.ndarray)

    def test_read_raises_on_failure(self):
        proxy, _ = self._make_proxy(read_ok=False)
        with patch('QVideo.lib._camera._open',
                   return_value=make_mock_noise_camera(read_ok=False)):
            with self.assertRaises(RuntimeError):
                proxy.read()

    def test_getattr_forwards_to_camera(self):
        proxy, cam = self._make_proxy()
        cam.fps = 30.
        with patch('QVideo.lib._camera._open', return_value=cam):
            result = proxy.fps
        self.assertEqual(result, 30.)

    def test_setattr_forwards_to_camera(self):
        proxy, cam = self._make_proxy()
        with patch('QVideo.lib._camera._open', return_value=cam):
            proxy.fps = 60.
        cam.__setattr__('fps', 60.)  # verify delegation happened
        self.assertEqual(cam.fps, 60.)

    def test_repr_shows_backend_label(self):
        proxy, cam = self._make_proxy()
        with patch('QVideo.lib._camera._open', return_value=cam):
            proxy._ensure_open()
        self.assertIn('Noise', repr(proxy))

    def test_ensure_open_skips_failed_backends(self):
        fail_cam = make_mock_noise_camera(open_ok=False)
        good_cam = make_mock_noise_camera(open_ok=True)
        proxy = _CameraProxy([('basler', 0), ('noise', 0)])
        side_effects = [fail_cam, good_cam]
        with patch('QVideo.lib._camera._open', side_effect=side_effects):
            proxy._ensure_open()
        self.assertEqual(
            object.__getattribute__(proxy, '_selected_key'), 'noise'
        )

    def test_ensure_open_raises_when_all_fail(self):
        fail_cam = make_mock_noise_camera(open_ok=False)
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.lib._camera._open', return_value=fail_cam):
            with self.assertRaises(RuntimeError):
                proxy._ensure_open()


class TestCameraFactory(unittest.TestCase):

    def test_returns_camera_proxy(self):
        cam = make_mock_noise_camera()
        with patch('QVideo.lib._camera._open', return_value=cam):
            result = Camera('noise')
        self.assertIsInstance(result, _CameraProxy)

    def test_no_model_returns_proxy(self):
        cam = make_mock_noise_camera()
        blocked = {_BACKENDS[k].module: None
                   for k in _BACKENDS if k != 'noise'}
        with patch.dict('sys.modules', blocked):
            with patch('QVideo.lib._camera._open', return_value=cam):
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
        with patch('QVideo.lib._camera._open', return_value=cam) as mock_open:
            proxy = Camera('noise', cameraID=2)
            proxy._ensure_open()
        mock_open.assert_called_once_with('noise', 2)

    def test_top_level_export(self):
        import QVideo
        self.assertIs(QVideo.Camera, Camera)

    def test_lib_export(self):
        from QVideo.lib import Camera as LibCamera
        self.assertIs(LibCamera, Camera)


class TestLiveView(unittest.TestCase):

    def _make_proxy(self):
        cam = make_mock_noise_camera()
        with patch('QVideo.lib._camera._open', return_value=cam):
            proxy = Camera('noise')
        return proxy, cam

    def test_live_view_returns_live_view_handle(self):
        from QVideo.lib._camera import _LiveView

        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        proxy, cam = self._make_proxy()
        with patch('QVideo.lib._camera._open', return_value=cam):
            with patch('ipywidgets.Image'):
                with patch('IPython.display.display'):
                    with patch('asyncio.ensure_future',
                               side_effect=_close_and_return):
                        lv = proxy.live_view()
        self.assertIsInstance(lv, _LiveView)

    def test_live_view_stop_cancels_task(self):
        from QVideo.lib._camera import _LiveView
        mock_task = MagicMock()
        lv = _LiveView(mock_task)
        lv.stop()
        mock_task.cancel.assert_called_once()

    def test_live_view_schedules_async_loop(self):
        proxy, cam = self._make_proxy()

        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        with patch('QVideo.lib._camera._open', return_value=cam):
            with patch('ipywidgets.Image'):
                with patch('IPython.display.display'):
                    with patch('asyncio.ensure_future',
                               side_effect=_close_and_return) as mock_future:
                        proxy.live_view()
        mock_future.assert_called_once()

    def test_live_view_stores_handle_on_proxy(self):
        from QVideo.lib._camera import _LiveView

        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        proxy, cam = self._make_proxy()
        with patch('QVideo.lib._camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('IPython.display.display'), \
             patch('asyncio.ensure_future', side_effect=_close_and_return):
            proxy.live_view()
        lv = object.__getattribute__(proxy, '_live_view')
        self.assertIsInstance(lv, _LiveView)

    def test_stop_live_view_cancels_task(self):
        mock_task = MagicMock()

        def _close_and_return(coro):
            coro.close()
            return mock_task

        proxy, cam = self._make_proxy()
        with patch('QVideo.lib._camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('IPython.display.display'), \
             patch('asyncio.ensure_future', side_effect=_close_and_return):
            proxy.live_view()
        proxy.stop_live_view()
        mock_task.cancel.assert_called_once()

    def test_stop_live_view_clears_handle(self):
        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        proxy, cam = self._make_proxy()
        with patch('QVideo.lib._camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('IPython.display.display'), \
             patch('asyncio.ensure_future', side_effect=_close_and_return):
            proxy.live_view()
        proxy.stop_live_view()
        self.assertIsNone(object.__getattribute__(proxy, '_live_view'))

    def test_stop_live_view_safe_when_no_feed(self):
        proxy, _ = self._make_proxy()
        proxy.stop_live_view()  # should not raise

    def test_live_view_raises_without_ipywidgets(self):
        proxy, _ = self._make_proxy()
        with patch.dict('sys.modules', {'ipywidgets': None}):
            with self.assertRaises(ImportError):
                proxy.live_view()

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

        with patch('QVideo.lib._camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('IPython.display.display'), \
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

        with patch('QVideo.lib._camera._open', return_value=cam), \
             patch('ipywidgets.Image'), \
             patch('IPython.display.display'), \
             patch('asyncio.ensure_future', side_effect=_close_and_return), \
             patch('cv2.imencode', side_effect=capture_imencode):
            proxy.live_view()

        self.assertTrue(len(encoded) > 0)
        self.assertEqual(encoded[0][0, 0], 128)


class TestJupyterChooser(unittest.TestCase):

    _WORKING_TWO = [('opencv', 0), ('noise', 0)]
    _WORKING_ONE = [('noise', 0)]

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
            patch('IPython.display.display'),
        )

    def test_single_camera_calls_report_and_returns(self):
        with patch.object(camera_module, '_jupyter_report') as mock_report:
            result = self._run(camera_module._jupyter_chooser(self._WORKING_ONE))
        mock_report.assert_called_once_with(self._WORKING_ONE)
        self.assertEqual(result, ('noise', 0))

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
                 patch('IPython.display.display'):
                return await camera_module._jupyter_chooser(self._WORKING_TWO)

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
                 patch('IPython.display.display') as mock_display:
                await camera_module._jupyter_chooser(self._WORKING_TWO)
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
                 patch('IPython.display.display'):
                return await camera_module._jupyter_chooser(self._WORKING_TWO)

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
                 patch('IPython.display.display'):
                await camera_module._jupyter_chooser(self._WORKING_TWO)

        self._run(run())
        self.assertTrue(mock_dropdown.disabled)
        self.assertTrue(mock_button.disabled)
        self.assertEqual(mock_button.button_style, '')

    def test_raises_import_error_without_ipywidgets(self):
        with patch.dict('sys.modules', {'ipywidgets': None}):
            with self.assertRaises(ImportError):
                self._run(camera_module._jupyter_chooser(self._WORKING_TWO))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
