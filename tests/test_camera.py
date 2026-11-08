'''Unit tests for interactive/camera.py and the table in chooser.py.'''
import asyncio
import contextlib
import copy
import importlib
import io
import logging
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
from qtpy import QtGui, QtWidgets

import QVideo.cameras.chooser as chooser_module
import QVideo.interactive.camera as camera_module
from QVideo.cameras.OpenCV import QOpenCVCamera
from QVideo.cameras.chooser import BACKENDS, discover, _probe
from QVideo.lib import _qapp
from QVideo.lib._qapp import ensure_qapp
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
        self.assertIsInstance(BACKENDS, dict)

    def test_required_backends_present(self):
        for key in ('basler', 'flir', 'ids', 'mv', 'vimbax',
                    'picamera', 'opencv', 'noise'):
            with self.subTest(key=key):
                self.assertIn(key, BACKENDS)

    def test_each_entry_names_its_module_classes_and_label(self):
        for key, entry in BACKENDS.items():
            with self.subTest(key=key):
                self.assertTrue(all(entry[:4]))

    def test_the_flag_and_help_come_together(self):
        for key, entry in BACKENDS.items():
            with self.subTest(key=key):
                self.assertEqual(bool(entry.flag), bool(entry.help))

    def test_noise_backend_points_to_correct_module(self):
        self.assertEqual(BACKENDS['noise'].module, 'QVideo.cameras.Noise')

    def test_opencv_backend_points_to_correct_module(self):
        self.assertEqual(BACKENDS['opencv'].module, 'QVideo.cameras.OpenCV')


class TestProbe(unittest.TestCase):

    def test_returns_true_for_importable_module(self):
        self.assertTrue(_probe('noise'))

    def test_returns_false_when_module_blocked(self):
        with patch.dict('sys.modules', {'QVideo.cameras.Basler': None}):
            self.assertFalse(_probe('basler'))


class TestDiscover(unittest.TestCase):

    def test_returns_noise_when_no_model_and_others_blocked(self):
        blocked = {k: None for k in BACKENDS if k != 'noise'}
        with patch.dict('sys.modules', {BACKENDS[k].module: None
                                        for k in blocked}):
            result = discover(None, 0)
        keys = [k for k, _ in result]
        self.assertIn('noise', keys)

    def test_model_none_returns_list_of_tuples(self):
        result = discover(None, 0)
        self.assertIsInstance(result, list)
        for item in result:
            self.assertEqual(len(item), 2)

    def test_model_noise_returns_noise_entry(self):
        result = discover('Noise', 0)
        self.assertEqual(result, [('noise', 0)])

    def test_model_opencv_returns_opencv_entry(self):
        result = discover('OpenCV', 0)
        self.assertEqual(result, [('opencv', 0)])

    def test_model_case_insensitive(self):
        self.assertEqual(discover('NOISE', 0), discover('noise', 0))
        self.assertEqual(discover('OpenCV', 0), discover('opencv', 0))

    def test_unknown_model_raises_value_error(self):
        with self.assertRaises(ValueError):
            discover('Unknown', 0)

    def test_returns_empty_when_model_module_blocked(self):
        with patch.dict('sys.modules', {'QVideo.cameras.Basler': None}):
            result = discover('basler', 0)
        self.assertEqual(result, [])

    def test_camera_id_preserved_in_result(self):
        result = discover('noise', 3)
        self.assertEqual(result, [('noise', 3)])


class TestCameraProxy(unittest.TestCase):

    def _make_proxy(self, open_ok=True, read_ok=True):
        cam = make_mock_noise_camera(open_ok=open_ok, read_ok=read_ok)
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            proxy = Camera('noise')
        return proxy, cam

    def test_read_returns_ndarray(self):
        proxy, _ = self._make_proxy()
        with patch('QVideo.cameras.chooser.create_camera',
                   return_value=make_mock_noise_camera()):
            frame = proxy.read()
        self.assertIsInstance(frame, np.ndarray)

    def test_read_raises_on_failure(self):
        proxy, _ = self._make_proxy(read_ok=False)
        with patch('QVideo.cameras.chooser.create_camera',
                   return_value=make_mock_noise_camera(read_ok=False)):
            with self.assertRaises(RuntimeError):
                proxy.read()

    def test_getattr_forwards_to_camera(self):
        proxy, cam = self._make_proxy()
        cam.fps = 30.
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            result = proxy.fps
        self.assertEqual(result, 30.)

    def test_setattr_forwards_to_camera(self):
        proxy, cam = self._make_proxy()
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            proxy.fps = 60.
        cam.__setattr__('fps', 60.)  # verify delegation happened
        self.assertEqual(cam.fps, 60.)

    def test_repr_shows_backend_label(self):
        proxy, cam = self._make_proxy()
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            proxy._ensure_open()
        self.assertIn('Noise', repr(proxy))

    def test_ensure_open_skips_failed_backends(self):
        fail_cam = make_mock_noise_camera(open_ok=False)
        good_cam = make_mock_noise_camera(open_ok=True)
        proxy = _CameraProxy([('basler', 0), ('noise', 0)])
        side_effects = [fail_cam, good_cam]
        with patch('QVideo.cameras.chooser.create_camera', side_effect=side_effects):
            proxy._ensure_open()
        self.assertEqual(
            object.__getattribute__(proxy, '_selected_key'), 'noise'
        )

    def test_ensure_open_raises_when_all_fail(self):
        fail_cam = make_mock_noise_camera(open_ok=False)
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.cameras.chooser.create_camera', return_value=fail_cam):
            with self.assertRaises(RuntimeError):
                proxy._ensure_open()

    def test_copying_a_proxy_does_not_open_a_camera(self):
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.cameras.chooser.create_camera') as create:
            twin = copy.copy(proxy)
        create.assert_not_called()
        self.assertIsInstance(twin, _CameraProxy)

    def test_a_double_underscore_name_is_not_forwarded(self):
        proxy, cam = self._make_proxy()
        with self.assertRaises(AttributeError):
            proxy.__wrapped__

    def test_a_notebook_probing_a_private_name_does_not_open_the_camera(self):
        # IPython looks for these when it displays an object.
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.cameras.chooser.create_camera') as create:
            for name in ('_repr_html_', '_repr_mimebundle_',
                         '_ipython_canary_method_should_not_exist_'):
                with self.subTest(name):
                    self.assertFalse(hasattr(proxy, name))
        create.assert_not_called()
        self.assertEqual(repr(proxy), '<Camera: uninitialized>')


class TestCameraFilters(unittest.TestCase):

    def _make_proxy(self, frames=None):
        cam = make_mock_noise_camera()
        if frames is not None:
            cam.saferead.side_effect = [(True, f) for f in frames]
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
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
        fake = MagicMock(
            side_effect=lambda read, fps, levels=None: shown.append(read()))
        with patch.object(_jupyter(), 'live_view', fake):
            proxy.live_view()
        self.assertTrue((shown[0] == 7).all())


class TestCameraFramesAndSave(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def make(self, frames=None, levels=None):
        cam = make_mock_noise_camera()
        cam.levels = levels
        if frames is not None:
            cam.saferead.side_effect = [(True, f) for f in frames]
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            proxy._ensure_open()
        return proxy, cam

    def counted(self, n, shape=(4, 6)):
        return [np.full(shape, i, np.uint8) for i in range(n)]

    def test_frames_reads_n_frames_in_order(self):
        proxy, _ = self.make(self.counted(3))
        frames = proxy.frames(3)
        self.assertEqual([int(f[0, 0]) for f in frames], [0, 1, 2])

    def test_frames_applies_the_filters(self):
        proxy, _ = self.make(self.counted(2))
        proxy.filters = [lambda f: f + 10]
        self.assertEqual([int(f[0, 0]) for f in proxy.frames(2)], [10, 11])

    def test_frames_takes_another_frame_for_a_filter_with_no_result(self):
        proxy, cam = self.make(self.counted(4))
        results = iter([None, 'a', None, 'b'])
        proxy.filters = [lambda f: next(results)]
        self.assertEqual(proxy.frames(2), ['a', 'b'])
        self.assertEqual(cam.saferead.call_count, 4)

    def test_n_must_be_at_least_one(self):
        proxy, _ = self.make()
        for n in (0, -1):
            with self.assertRaises(ValueError):
                proxy.frames(n)
            with self.assertRaises(ValueError):
                proxy.stack(n)

    def test_stack_joins_the_frames_on_a_new_first_axis(self):
        proxy, _ = self.make(self.counted(3))
        stack = proxy.stack(3)
        self.assertEqual(stack.shape, (3, 4, 6))
        self.assertEqual(int(stack[2, 0, 0]), 2)

    def test_stack_of_color_frames(self):
        proxy, _ = self.make(self.counted(2, (4, 6, 3)))
        self.assertEqual(proxy.stack(2).shape, (2, 4, 6, 3))

    def test_a_failed_read_raises(self):
        proxy, cam = self.make()
        cam.saferead.return_value = (False, None)
        with self.assertRaises(RuntimeError):
            proxy.frames(2)

    def test_save_writes_a_new_frame_to_the_named_file(self):
        frame = np.arange(24, dtype=np.uint8).reshape(4, 6)
        proxy, _ = self.make([frame])
        name = str(self.folder / 'a.png')
        self.assertEqual(proxy.save(name), name)
        loaded = QtGui.QImage(name)
        self.assertEqual(loaded.pixelColor(3, 2).red(), frame[2, 3])

    def test_save_accepts_a_path(self):
        proxy, _ = self.make(self.counted(1))
        name = self.folder / 'b.png'
        self.assertEqual(proxy.save(name), str(name))
        self.assertTrue(name.exists())

    def test_save_without_a_name_makes_one_in_the_current_directory(self):
        proxy, _ = self.make(self.counted(2))
        with contextlib.chdir(self.folder):
            first = proxy.save()
            second = proxy.save()
        self.assertEqual(Path(first).parent.resolve(), self.folder.resolve())
        self.assertTrue(Path(first).name.startswith('camera_'))
        self.assertNotEqual(first, second)
        self.assertEqual(len(list(self.folder.glob('camera_*.png'))), 2)

    def test_save_writes_the_image_that_it_is_given(self):
        proxy, cam = self.make()
        image = np.full((4, 6), 77, np.uint8)
        cam.saferead.reset_mock()
        name = str(self.folder / 'c.png')
        proxy.save(name, image)
        cam.saferead.assert_not_called()
        self.assertEqual(QtGui.QImage(name).pixelColor(0, 0).red(), 77)

    def test_save_applies_the_filters_to_the_frame_it_reads(self):
        proxy, _ = self.make(self.counted(1))
        proxy.filters = [lambda f: f + 9]
        name = str(self.folder / 'd.png')
        proxy.save(name)
        self.assertEqual(QtGui.QImage(name).pixelColor(0, 0).red(), 9)

    def test_a_deep_frame_is_stretched_by_the_levels_of_the_camera(self):
        frame = np.full((4, 6), 4095, np.uint16)
        proxy, _ = self.make([frame], levels=(0., 4095.))
        name = str(self.folder / 'e.png')
        proxy.save(name)
        loaded = QtGui.QImage(name)
        self.assertEqual(loaded.depth(), 16)
        self.assertEqual(loaded.pixelColor(0, 0).red(), 255)

    def test_save_raises_for_an_image_that_cannot_be_saved(self):
        proxy, _ = self.make()
        with self.assertRaises(ValueError):
            proxy.save(str(self.folder / 'f.png'),
                       np.zeros((4, 6), np.float32))

    def test_save_raises_for_a_file_that_cannot_be_written(self):
        proxy, _ = self.make(self.counted(1))
        with self.assertRaises(OSError):
            proxy.save('/nonexistent-folder/g.png')


class TestCameraRecord(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def make(self, shape=(16, 16), dtype=np.uint8, levels=None, fps=20.):
        cam = make_mock_noise_camera()
        cam.levels = levels
        cam.fps = fps
        self.count = 0

        def read():
            self.count += 1
            return True, np.full(shape, self.count, dtype)
        cam.saferead.side_effect = read
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            proxy._ensure_open()
        return proxy, cam

    def video(self, path):
        from QVideo.dvr import formats
        video = formats.openVideo(path)
        self.addCleanup(video.close)  # Windows cannot delete an open file
        return video

    def test_n_frames_are_recorded_and_the_path_returned(self):
        proxy, _ = self.make()
        name = str(self.folder / 'a.mkv')
        self.assertEqual(proxy.record(name, n=5), name)
        video = self.video(name)
        self.assertEqual(len(video), 5)
        self.assertEqual(int(video[3][0, 0, 0]) if video[3].ndim == 3
                         else int(video[3][0, 0]), 4)

    def test_it_takes_a_path(self):
        proxy, _ = self.make()
        name = self.folder / 'b.mkv'
        self.assertEqual(proxy.record(name, n=2), str(name))
        self.assertTrue(name.exists())

    def test_it_stops_after_the_seconds(self):
        proxy, cam = self.make()
        cam.saferead.side_effect = (
            lambda: (time.sleep(0.01), (True, np.zeros((16, 16), np.uint8)))[1])
        start = time.perf_counter()
        proxy.record(self.folder / 'c.mkv', seconds=0.1)
        self.assertLess(time.perf_counter() - start, 1.)
        self.assertGreaterEqual(len(self.video(str(self.folder / 'c.mkv'))),
                                2)

    def test_the_first_limit_ends_it(self):
        proxy, _ = self.make()
        proxy.record(self.folder / 'd.mkv', n=3, seconds=60)
        self.assertEqual(len(self.video(str(self.folder / 'd.mkv'))), 3)

    def test_the_filters_are_applied(self):
        proxy, _ = self.make()
        proxy.filters = [lambda f: f + 100]
        name = str(self.folder / 'e.h5')
        proxy.record(name, n=2)
        self.assertEqual(int(np.asarray(self.video(name)[0]).flat[0]), 101)

    def test_the_file_declares_the_frame_rate_of_the_camera(self):
        proxy, _ = self.make(fps=25.)
        with patch('QVideo.dvr.formats.writerClass') as lookup:
            writer = lookup.return_value.return_value
            writer.finished = MagicMock()
            proxy.record(self.folder / 'f.mkv', n=1)
        self.assertEqual(lookup.return_value.call_args.kwargs['fps'], 25.)

    def test_fps_can_be_given(self):
        proxy, _ = self.make(fps=25.)
        with patch('QVideo.dvr.formats.writerClass') as lookup:
            lookup.return_value.return_value.finished = MagicMock()
            proxy.record(self.folder / 'g.mkv', n=1, fps=10)
        self.assertEqual(lookup.return_value.call_args.kwargs['fps'], 10)

    def test_a_deep_frame_keeps_its_counts_in_a_lossless_file(self):
        proxy, _ = self.make(dtype=np.uint16, levels=(0., 4095.))
        name = str(self.folder / 'h.h5')
        proxy.record(name, n=2)
        self.assertEqual(self.video(name)[0].dtype, np.uint16)

    def test_the_levels_travel_with_a_deep_frame(self):
        proxy, _ = self.make(dtype=np.uint16, levels=(0., 4095.))
        with patch('QVideo.dvr.formats.writerClass') as lookup:
            writer = lookup.return_value.return_value
            writer.finished = MagicMock()
            proxy.record(self.folder / 'i.mkv', n=1)
        info = writer.write.call_args.args[1]
        self.assertEqual(info.levels, (0., 4095.))

    def test_it_needs_a_limit(self):
        proxy, _ = self.make()
        with self.assertRaises(ValueError):
            proxy.record(self.folder / 'j.mkv')

    def test_the_limits_must_be_positive(self):
        proxy, _ = self.make()
        with self.assertRaises(ValueError):
            proxy.record(self.folder / 'k.mkv', n=0)
        with self.assertRaises(ValueError):
            proxy.record(self.folder / 'k.mkv', seconds=0)

    def test_an_unsupported_extension_raises(self):
        proxy, cam = self.make()
        with self.assertRaises(ValueError):
            proxy.record(self.folder / 'l.xyz', n=1)
        cam.saferead.assert_not_called()

    def test_an_existing_file_is_not_replaced(self):
        proxy, _ = self.make()
        name = self.folder / 'm.mkv'
        name.write_bytes(b'old')
        with self.assertRaises(FileExistsError):
            proxy.record(name, n=1)
        self.assertEqual(name.read_bytes(), b'old')

    def test_overwrite_replaces_it(self):
        proxy, _ = self.make()
        name = self.folder / 'n.mkv'
        name.write_bytes(b'old')
        proxy.record(name, n=2, overwrite=True)
        self.assertEqual(len(self.video(str(name))), 2)

    def test_a_failed_read_raises_and_closes_the_file(self):
        proxy, cam = self.make()
        good = cam.saferead.side_effect
        calls = iter(range(100))

        def read():
            if next(calls) >= 2:
                return False, None
            return good()
        cam.saferead.side_effect = read
        name = str(self.folder / 'o.h5')
        with self.assertRaises(RuntimeError):
            proxy.record(name, n=5)
        self.assertEqual(len(self.video(name)), 2)

    def test_an_interrupt_closes_the_file(self):
        proxy, cam = self.make()
        good = cam.saferead.side_effect
        calls = iter(range(100))

        def read():
            if next(calls) >= 3:
                raise KeyboardInterrupt
            return good()
        cam.saferead.side_effect = read
        name = str(self.folder / 'p.h5')
        with self.assertRaises(KeyboardInterrupt):
            proxy.record(name, n=10)
        self.assertEqual(len(self.video(name)), 3)

    def test_a_writer_that_stops_raises_with_the_reason(self):
        proxy, cam = self.make()
        good = cam.saferead.side_effect
        calls = iter(range(100))

        def read():
            if next(calls) >= 2:
                return True, np.zeros((8, 8), np.uint8)  # a new size
            return good()
        cam.saferead.side_effect = read
        with self.assertRaises(RuntimeError) as caught:
            proxy.record(self.folder / 'q.mkv', n=5)
        self.assertIn('size changed', str(caught.exception))

    def clock(self, step):
        """A clock that advances *step* seconds each time it is read."""
        now = [0.]

        def perf_counter():
            now[0] += step
            return now[0]
        return patch.object(camera_module, 'time',
                            types.SimpleNamespace(perf_counter=perf_counter))

    def record_at(self, step, fps=20., **kwargs):
        proxy, _ = self.make(fps=fps)
        with self.clock(step):
            proxy.record(self.folder / 'rate.mkv', n=5, **kwargs)

    def test_frames_at_the_rate_of_the_file_are_not_remarked_on(self):
        with self.assertNoLogs('QVideo.interactive.camera', 'WARNING'):
            self.record_at(0.05)

    def test_a_small_difference_in_rate_is_not_remarked_on(self):
        with self.assertNoLogs('QVideo.interactive.camera', 'WARNING'):
            self.record_at(1 / 21)

    def test_slow_frames_are_reported_with_the_measured_rate(self):
        with self.assertLogs('QVideo.interactive.camera', 'WARNING') as logs:
            self.record_at(0.1)
        text = logs.output[0]
        self.assertIn('10.0 frames/s', text)
        self.assertIn('20.0', text)
        self.assertIn('fps=10.0', text)
        self.assertIn('2.0 times as fast', text)

    def test_fast_frames_are_reported_too(self):
        with self.assertLogs('QVideo.interactive.camera', 'WARNING') as logs:
            self.record_at(0.01)
        self.assertIn('fps=100.0', logs.output[0])

    def test_a_rate_that_was_given_is_not_questioned(self):
        proxy, _ = self.make(fps=20.)
        with self.clock(0.1), \
                self.assertNoLogs('QVideo.interactive.camera', 'WARNING'):
            proxy.record(self.folder / 'given.mkv', n=5, fps=20)

    def test_one_frame_has_no_rate(self):
        proxy, _ = self.make()
        with self.clock(0.5), \
                self.assertNoLogs('QVideo.interactive.camera', 'WARNING'):
            proxy.record(self.folder / 'one.mkv', n=1)


class TestShowAndLevels(unittest.TestCase):

    def png(self, call):
        shown = []
        with patch('QVideo.interactive.widgets._display', shown.append):
            call()
        data = shown[0].data
        self.assertTrue(data.startswith(b'\x89PNG'))
        return cv2.imdecode(np.frombuffer(data, np.uint8),
                            cv2.IMREAD_UNCHANGED)

    def deep(self, white=4095):
        frame = np.zeros((20, 20), np.uint16)
        frame[:, 10:] = white
        return frame

    def test_an_8_bit_frame_is_shown_as_it_is(self):
        frame = np.arange(400, dtype=np.uint8).reshape(20, 20)
        picture = self.png(lambda: _jupyter().show(frame))
        np.testing.assert_array_equal(picture, frame)

    def test_a_deep_frame_is_stretched_by_its_percentiles(self):
        picture = self.png(lambda: _jupyter().show(self.deep()))
        self.assertEqual(int(picture[0, 0]), 0)
        self.assertEqual(int(picture[0, 19]), 255)

    def test_camera_contrast_uses_the_levels_of_the_camera(self):
        frame = self.deep(2000)
        picture = self.png(lambda: _jupyter().show(
            frame, 'camera', (0., 4000.)))
        self.assertAlmostEqual(int(picture[0, 19]), 127, delta=2)

    def test_full_contrast_uses_the_whole_16_bits(self):
        picture = self.png(lambda: _jupyter().show(self.deep(), 'full'))
        self.assertLess(int(picture[0, 19]), 20)

    def test_contrast_can_be_a_pair_of_levels(self):
        picture = self.png(lambda: _jupyter().show(
            self.deep(1000), (0, 2000)))
        self.assertAlmostEqual(int(picture[0, 19]), 127, delta=2)

    def test_a_color_frame_is_shown_in_color(self):
        frame = np.zeros((8, 8, 3), np.uint8)
        frame[..., 0] = 200
        picture = self.png(lambda: _jupyter().show(frame))
        self.assertEqual(int(picture[0, 0, 2]), 200)  # OpenCV is BGR

    def test_a_contrast_that_is_unknown_raises(self):
        with self.assertRaises(ValueError):
            _jupyter().show(self.deep(), 'bright')

    def make_proxy(self, frame, levels=(0., 4095.)):
        cam = make_mock_noise_camera()
        cam.levels = levels
        cam.saferead.return_value = (True, frame)
        proxy = _CameraProxy([('noise', 0)])
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            proxy._ensure_open()
        return proxy, cam

    def test_the_proxy_shows_a_new_frame_with_the_levels_of_the_camera(self):
        frame = self.deep()
        proxy, _ = self.make_proxy(frame)
        with patch.object(_jupyter(), 'show') as show:
            proxy.show()
        shown, contrast, levels = show.call_args.args
        np.testing.assert_array_equal(shown, frame)
        self.assertEqual((contrast, levels), ('auto', (0., 4095.)))

    def test_the_proxy_shows_the_image_it_is_given(self):
        proxy, cam = self.make_proxy(self.deep())
        image = np.zeros((4, 4), np.uint8)
        cam.saferead.reset_mock()
        with patch.object(_jupyter(), 'show') as show:
            proxy.show(image, 'full')
        cam.saferead.assert_not_called()
        self.assertIs(show.call_args.args[0], image)
        self.assertEqual(show.call_args.args[1], 'full')

    def run_live(self, frame, levels=None, mode=None, reads=3):
        """Run a live view over *reads* frames; return (shown, widget)."""
        from QVideo.interactive.widgets import live_view
        shown = []
        calls = []

        def read():
            calls.append(1)
            if len(calls) > reads:
                raise RuntimeError('done')
            return frame

        async def run():
            with patch('QVideo.interactive.widgets._display', shown.append):
                task = live_view(read, fps=1000, levels=levels)._task
                if mode is not None:
                    shown[0].children[1].value = mode
                await asyncio.wait_for(task, timeout=5)

        with self.assertLogs('QVideo.interactive.widgets', 'WARNING'):
            asyncio.run(run())
        return shown

    def test_an_8_bit_live_view_has_no_levels_control(self):
        import ipywidgets
        shown = self.run_live(np.zeros((8, 8), np.uint8))
        self.assertIsInstance(shown[0], ipywidgets.Image)

    def test_a_deep_live_view_offers_the_levels(self):
        import ipywidgets
        shown = self.run_live(self.deep(), lambda: (0., 4095.))
        box = shown[0]
        self.assertIsInstance(box, ipywidgets.VBox)
        dropdown = box.children[1]
        self.assertEqual([v for _, v in dropdown.options],
                         ['camera', 'auto', 'full'])
        self.assertEqual(dropdown.value, 'camera')

    def jpeg(self, widget):
        return cv2.imdecode(np.frombuffer(widget.value, np.uint8),
                            cv2.IMREAD_GRAYSCALE)

    def test_the_choice_changes_what_is_shown(self):
        camera = self.run_live(self.deep(), lambda: (0., 4095.))
        full = self.run_live(self.deep(), lambda: (0., 4095.), mode='full')
        self.assertGreater(int(self.jpeg(camera[0].children[0])[0, 19]), 240)
        self.assertLess(int(self.jpeg(full[0].children[0])[0, 19]), 20)

    def test_a_deep_live_view_without_levels_uses_the_full_range(self):
        shown = self.run_live(self.deep(65535))
        self.assertGreater(int(self.jpeg(shown[0].children[0])[0, 19]), 240)

    def test_the_proxy_gives_the_live_view_the_levels_of_the_camera(self):
        proxy, cam = self.make_proxy(self.deep())
        with patch.object(_jupyter(), 'live_view') as live:
            proxy.live_view()
        self.assertEqual(live.call_args.kwargs['levels'](), (0., 4095.))
        cam.levels = (0., 1023.)
        self.assertEqual(live.call_args.kwargs['levels'](), (0., 1023.))


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

    def setUp(self):
        # These tests are about importing the backend: the Flir camera
        # would otherwise open in a worker, and on this machine for real.
        patcher = patch.object(chooser_module, 'uses_worker',
                               return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_open_records_exception(self):
        errors = []
        boom = RuntimeError('GENICAM_GENTL64_PATH is not set')
        with patch('importlib.import_module', side_effect=boom):
            self.assertIsNone(chooser_module.create_camera('flir', 0, errors))
        self.assertEqual(errors, [('Flir', boom)])

    def test_open_logs_where_the_failure_was(self):
        boom = RuntimeError('Feature not present')
        with patch('importlib.import_module', side_effect=boom):
            with self.assertLogs('QVideo.cameras.chooser', 'DEBUG') as logs:
                chooser_module.create_camera('flir', 0, [])
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
                    with chooser_module.quiet():
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
            errors.append((BACKENDS[key].label, RuntimeError(f'why {key}')))
        with patch('QVideo.cameras.chooser.create_camera', side_effect=fake_open):
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
        with patch('QVideo.cameras.chooser.create_camera', side_effect=fake_open):
            with self.assertLogs('QVideo.cameras.chooser', 'WARNING') as logs:
                proxy._ensure_open()
        self.assertIn('Flir: no producer', logs.output[0])

    def test_closed_camera_is_reported(self):
        proxy = _CameraProxy([('flir', 0)])
        with patch('QVideo.cameras.chooser.create_camera',
                   return_value=make_mock_noise_camera(open_ok=False)):
            with self.assertRaisesRegex(RuntimeError, 'Flir: device failed'):
                proxy._ensure_open()

    def test_explicit_model_reports_import_failure(self):
        with patch('QVideo.cameras.chooser._probe', return_value=False), \
             patch('importlib.import_module',
                   side_effect=ImportError('pip install genicam harvesters')):
            with self.assertRaisesRegex(RuntimeError, 'pip install genicam'):
                Camera('flir')


class TestCameraFactory(unittest.TestCase):

    def test_returns_camera_proxy(self):
        cam = make_mock_noise_camera()
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            result = Camera('noise')
        self.assertIsInstance(result, _CameraProxy)

    def test_no_model_returns_proxy(self):
        cam = make_mock_noise_camera()
        blocked = {BACKENDS[k].module: None
                   for k in BACKENDS if k != 'noise'}
        with patch.dict('sys.modules', blocked):
            with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
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
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam) as mock_open:
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
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            proxy = Camera('noise')
        return proxy, cam

    def test_live_view_returns_live_view_handle(self):
        from QVideo.interactive.widgets import LiveView

        def _close_and_return(coro):
            coro.close()
            return MagicMock()

        proxy, cam = self._make_proxy()
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
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

        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
            with patch('ipywidgets.Image'):
                with patch('QVideo.interactive.widgets._display'):
                    with patch('asyncio.ensure_future', side_effect=_keep):
                        proxy.live_view()
        cam.saferead.return_value = (False, None)  # the camera went away
        with self.assertLogs('QVideo.interactive.widgets', 'WARNING') as logs:
            asyncio.run(asyncio.wait_for(loops[0], timeout=5))
        self.assertIn('Camera read failed', logs.output[0])

    def test_live_view_reads_off_the_event_loop_thread(self):
        import threading
        from QVideo.interactive.widgets import live_view
        threads = []
        frame = np.zeros((4, 4), dtype=np.uint8)

        def read():
            threads.append(threading.get_ident())
            if len(threads) > 2:
                raise RuntimeError('done')
            return frame

        async def run():
            main = threading.get_ident()
            with patch('ipywidgets.Image'), \
                 patch('QVideo.interactive.widgets._display'):
                task = live_view(read, fps=1000)._task
                await asyncio.wait_for(task, timeout=5)
            return main

        with self.assertLogs('QVideo.interactive.widgets', 'WARNING'):
            main = asyncio.run(run())
        self.assertEqual(threads[0], main)  # the first frame sizes the widget
        self.assertNotIn(main, threads[1:])

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

        with patch('QVideo.cameras.chooser.create_camera', return_value=cam):
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
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam), \
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
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam), \
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
        with patch('QVideo.cameras.chooser.create_camera', return_value=cam), \
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
             patch.object(chooser_module, 'create_camera', return_value=cam):
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

        with patch('QVideo.cameras.chooser.create_camera', return_value=cam), \
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

        with patch('QVideo.cameras.chooser.create_camera', return_value=cam), \
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
        kept = []
        with patch('qtpy.QtWidgets.QApplication', fake), \
                patch.object(_qapp, '_keep', kept):
            ensure_qapp()
        fake.assert_called_once_with([])
        self.assertEqual(kept, [fake.return_value])   # kept alive

    def test_an_existing_qapplication_is_kept(self):
        fake = MagicMock()
        with patch('qtpy.QtWidgets.QApplication', fake):
            ensure_qapp()
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
        with patch.object(chooser_module, 'create_camera',
                          side_effect=lambda key, i, errors=None: cameras[key]):
            working = chooser_module.working(
                [('noise', 0), ('opencv', 0), ('flir', 0)])
        self.assertEqual(working, [('noise', 0)])
        good.close.assert_called_once_with()
        bad.close.assert_not_called()

    def test_available_cameras_name_each_working_device(self):
        names = {0: 'Front', 1: 'Back'}
        with patch.object(chooser_module, 'discover',
                          return_value=[('opencv', 0), ('noise', 0)]), \
                patch.object(QOpenCVCamera, 'deviceNames',
                             return_value=names), \
                patch.object(chooser_module, 'working',
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
                         f"Camera: {BACKENDS['noise'].label}\n")

    def test_several_cameras_say_how_to_pick_another(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            camera_module._report([('opencv', 0), ('noise', 0)])
        text = out.getvalue()
        self.assertIn(f"Using {BACKENDS['opencv'].label}", text)
        self.assertIn(f"Camera('{BACKENDS['noise'].label}')", text)

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
            patch.object(chooser_module, 'working',
                         return_value=working),
            patch('QVideo.cameras.chooser.create_camera', return_value=cam)]
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
        chooser_module.working.assert_not_called()


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
