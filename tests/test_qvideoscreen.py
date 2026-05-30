'''Unit tests for QVideoScreen.'''
import unittest
import numpy as np
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets, QtTest
from QVideo.lib.QVideoScreen import QVideoScreen
from QVideo.lib.QFilterBank import QFilterBank


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


def make_mock_source(fps=30., width=640, height=480):
    '''Return a MagicMock standing in for a QVideoSource.'''
    source = MagicMock()
    source.shape = QtCore.QSize(width, height)
    source.fps = fps
    return source


def _spy(screen, signal_name='newFrame'):
    return QtTest.QSignalSpy(getattr(screen, signal_name))


def make_screen(**kwargs) -> QVideoScreen:
    '''Return a QVideoScreen with default parameters.'''
    return QVideoScreen(**kwargs)


class TestInit(unittest.TestCase):

    def test_ready_on_init(self):
        screen = make_screen()
        self.assertTrue(screen._ready)

    def test_pending_none_on_init(self):
        screen = make_screen()
        self.assertIsNone(screen._pending)

    def test_source_none_on_init(self):
        screen = make_screen()
        self.assertIsNone(screen._source)

    def test_has_timer(self):
        screen = make_screen()
        self.assertIsInstance(screen._timer, QtCore.QTimer)

    def test_filter_is_filterbank(self):
        screen = make_screen()
        self.assertIsInstance(screen.filter, QFilterBank)

    def test_filter_initially_hidden(self):
        screen = make_screen()
        self.assertFalse(screen.filter.isVisible())


class TestFramerate(unittest.TestCase):

    def test_default_framerate_is_none(self):
        screen = make_screen()
        self.assertIsNone(screen.framerate)

    def test_default_interval_is_zero(self):
        screen = make_screen()
        self.assertEqual(screen._interval, 0)

    def test_framerate_setter_stores_value(self):
        screen = make_screen(framerate=60)
        self.assertEqual(screen.framerate, 60)

    def test_framerate_setter_computes_interval(self):
        screen = make_screen(framerate=25)
        self.assertEqual(screen._interval, int(1000 / 25))

    def test_framerate_none_sets_interval_zero(self):
        screen = make_screen(framerate=30)
        screen.framerate = None
        self.assertEqual(screen._interval, 0)

    def test_framerate_zero_raises(self):
        screen = make_screen()
        with self.assertRaises(ValueError):
            screen.framerate = 0

    def test_framerate_negative_raises(self):
        screen = make_screen()
        with self.assertRaises(ValueError):
            screen.framerate = -10


class TestSource(unittest.TestCase):

    def test_source_stored(self):
        screen = make_screen()
        source = make_mock_source()
        screen.source = source
        self.assertIs(screen.source, source)

    def test_source_calls_update_shape(self):
        screen = make_screen()
        source = make_mock_source(width=1280, height=720)
        with patch.object(screen, 'updateShape') as mock_update:
            screen.source = source
        mock_update.assert_called_once_with(QtCore.QSize(1280, 720))

    def test_source_connects_shape_changed(self):
        screen = make_screen()
        source = make_mock_source()
        screen.source = source
        source.shapeChanged.connect.assert_called_once_with(screen.updateShape)

    def test_source_connects_new_frame(self):
        screen = make_screen()
        source = make_mock_source()
        screen.source = source
        source.newFrame.connect.assert_called_once_with(screen.setImage)

    def test_source_disconnects_old_shape_changed(self):
        screen = make_screen()
        old_source = make_mock_source()
        screen.source = old_source
        screen.source = make_mock_source()
        old_source.shapeChanged.disconnect.assert_called_once_with(screen.updateShape)

    def test_source_disconnects_old_new_frame(self):
        screen = make_screen()
        old_source = make_mock_source()
        screen.source = old_source
        screen.source = make_mock_source()
        old_source.newFrame.disconnect.assert_called_once_with(screen.setImage)

    def test_source_no_disconnect_when_none(self):
        '''Setting source for the first time should not attempt to disconnect.'''
        screen = make_screen()
        source = make_mock_source()
        try:
            screen.source = source
        except AttributeError:
            self.fail('source setter called disconnect on None')

    def test_source_none_clears_source(self):
        screen = make_screen()
        screen.source = make_mock_source()
        screen.source = None
        self.assertIsNone(screen._source)

    def test_source_none_no_crash(self):
        '''Setting source to None after a source is connected should not raise.'''
        screen = make_screen()
        screen.source = make_mock_source()
        try:
            screen.source = None
        except Exception as e:
            self.fail(f'Setting source to None raised {e}')


class TestSetImage(unittest.TestCase):

    def test_setimage_when_ready_calls_filter(self):
        screen = make_screen()
        with patch.object(QFilterBank, '__call__', return_value=_FRAME) as mock_filter:
            with patch.object(screen.image, 'setImage'):
                screen.setImage(_FRAME)
        mock_filter.assert_called_once()

    def test_setimage_when_ready_updates_display(self):
        screen = make_screen()
        with patch.object(screen.filter, '__call__', return_value=_FRAME):
            with patch.object(screen.image, 'setImage') as mock_set:
                screen.setImage(_FRAME)
        mock_set.assert_called_once_with(_FRAME, autoLevels=False)

    def test_setimage_when_ready_sets_not_ready(self):
        screen = make_screen()
        with patch.object(screen.filter, '__call__', return_value=_FRAME):
            with patch.object(screen.image, 'setImage'):
                screen.setImage(_FRAME)
        self.assertFalse(screen._ready)

    def test_setimage_arms_timer(self):
        screen = make_screen()
        with patch.object(screen.filter, '__call__', return_value=_FRAME):
            with patch.object(screen.image, 'setImage'):
                with patch.object(screen._timer, 'start') as mock_start:
                    screen.setImage(_FRAME)
        mock_start.assert_called_once_with(screen._interval)

    def test_setimage_when_ready_clears_pending(self):
        screen = make_screen()
        screen._pending = _FRAME.copy()
        with patch.object(QFilterBank, '__call__', return_value=_FRAME):
            with patch.object(screen.image, 'setImage'):
                screen.setImage(_FRAME)
        self.assertIsNone(screen._pending)

    def test_setimage_when_not_ready_buffers_frame(self):
        screen = make_screen()
        screen._ready = False
        screen.setImage(_FRAME)
        self.assertIs(screen._pending, _FRAME)

    def test_setimage_when_not_ready_skips_display(self):
        screen = make_screen()
        screen._ready = False
        with patch.object(screen.image, 'setImage') as mock_set:
            screen.setImage(_FRAME)
        mock_set.assert_not_called()

    def test_setimage_when_not_ready_leaves_not_ready(self):
        screen = make_screen()
        screen._ready = False
        with patch.object(screen.image, 'setImage'):
            screen.setImage(_FRAME)
        self.assertFalse(screen._ready)



class TestSetready(unittest.TestCase):

    def test_setready_restores_ready(self):
        screen = make_screen()
        screen._ready = False
        screen._setready()
        self.assertTrue(screen._ready)

    def test_setready_displays_pending_frame(self):
        screen = make_screen()
        screen._ready = False
        screen._pending = _FRAME.copy()
        with patch.object(QFilterBank, '__call__', return_value=_FRAME):
            with patch.object(screen.image, 'setImage') as mock_set:
                screen._setready()
        mock_set.assert_called_once()

    def test_setready_clears_pending_after_display(self):
        screen = make_screen()
        screen._ready = False
        screen._pending = _FRAME.copy()
        with patch.object(QFilterBank, '__call__', return_value=_FRAME):
            with patch.object(screen.image, 'setImage'):
                screen._setready()
        # setImage owns clearing _pending when it runs in the _ready branch
        self.assertIsNone(screen._pending)

    def test_setready_no_pending_leaves_ready(self):
        screen = make_screen()
        screen._ready = False
        screen._pending = None
        screen._setready()
        self.assertTrue(screen._ready)


class TestSizeHints(unittest.TestCase):

    def setUp(self):
        self.screen = make_screen()
        self.shape = QtCore.QSize(640, 480)
        self.source = make_mock_source(width=640, height=480)
        with patch.object(self.screen, 'updateShape'):
            self.screen._source = self.source
        # Simulate updateShape having been called with the source shape.
        self.screen._videoShape = self.shape

    def test_size_hint_returns_video_shape(self):
        self.assertEqual(self.screen.sizeHint(), self.shape)

    def test_has_height_for_width_true_when_shape_known(self):
        self.assertTrue(self.screen.hasHeightForWidth())

    def test_has_height_for_width_false_before_any_source(self):
        screen = make_screen()
        self.assertFalse(screen.hasHeightForWidth())

    def test_has_height_for_width_true_after_update_shape(self):
        screen = make_screen()
        screen.updateShape(QtCore.QSize(640, 480))
        self.assertTrue(screen.hasHeightForWidth())

    def test_height_for_width_preserves_aspect_ratio(self):
        # 640×480 → height for width=320 should be 240
        self.assertEqual(self.screen.heightForWidth(320), 240)

    def test_height_for_width_without_shape_delegates(self):
        screen = make_screen()
        try:
            screen.heightForWidth(320)
        except Exception as e:
            self.fail(f'heightForWidth raised {e} without shape')


    def test_size_hint_without_shape_delegates(self):
        screen = make_screen()
        result = screen.sizeHint()
        self.assertIsInstance(result, QtCore.QSize)


class TestResizeEvent(unittest.TestCase):

    def test_resize_event_does_not_call_fit_to_video(self):
        '''resizeEvent must not queue _fitToVideo; doing so creates a
        resize→fitToVideo→resize feedback loop that causes visible jitter
        when the user drags the window border.'''
        screen = make_screen()
        with patch.object(screen, '_fitToVideo') as mock_fit:
            screen.resizeEvent(MagicMock())
        mock_fit.assert_not_called()

    def test_resize_event_sets_range_when_shape_known(self):
        screen = make_screen()
        screen._videoShape = QtCore.QSize(640, 480)
        with patch.object(screen.view, 'setRange') as mock_range:
            screen.resizeEvent(MagicMock())
        mock_range.assert_called_once_with(
            xRange=(0, 640), yRange=(0, 480), padding=0, update=True)

    def test_resize_event_does_not_set_range_without_shape(self):
        screen = make_screen()
        with patch.object(screen.view, 'setRange') as mock_range:
            screen.resizeEvent(MagicMock())
        mock_range.assert_not_called()


class TestFitToVideo(unittest.TestCase):

    def _make_mock_window(self, win_w, win_h, sh_w=None, sh_h=None):
        mock_win = MagicMock()
        mock_win.width.return_value = win_w
        mock_win.height.return_value = win_h
        mock_win.pos.return_value = QtCore.QPoint(0, 0)
        mock_win.sizeHint.return_value = QtCore.QSize(
            sh_w if sh_w is not None else win_w,
            sh_h if sh_h is not None else win_h)
        return mock_win

    @contextmanager
    def _mock_screen(self, screen_w=2560, screen_h=1600):
        mock_qscreen = MagicMock()
        mock_qscreen.availableGeometry.return_value = QtCore.QRect(
            0, 0, screen_w, screen_h)
        with patch.object(QtWidgets.QApplication, 'primaryScreen',
                          return_value=mock_qscreen), \
             patch.object(QtWidgets.QApplication, 'screenAt',
                          return_value=mock_qscreen):
            yield

    def test_no_shape_skips_resize(self):
        screen = make_screen()
        with patch.object(screen, 'window') as mock_win_fn:
            screen._fitToVideo()
        mock_win_fn.assert_not_called()

    def test_resizes_window_to_native_video_size(self):
        screen = make_screen()
        screen._videoShape = QtCore.QSize(1280, 1024)
        mock_win = self._make_mock_window(640, 480, sh_w=1280, sh_h=1024)
        with patch.object(screen, 'window', return_value=mock_win), \
             self._mock_screen():
            screen._fitToVideo()
        mock_win.resize.assert_called_once_with(1280, 1024)

    def test_resizes_width_not_just_height(self):
        screen = make_screen()
        screen._videoShape = QtCore.QSize(1280, 1024)
        mock_win = self._make_mock_window(320, 256, sh_w=1280, sh_h=1024)
        with patch.object(screen, 'window', return_value=mock_win), \
             self._mock_screen():
            screen._fitToVideo()
        new_w = mock_win.resize.call_args[0][0]
        self.assertGreater(new_w, 320)

    def test_no_resize_if_already_correct(self):
        screen = make_screen()
        screen._videoShape = QtCore.QSize(640, 480)
        mock_win = self._make_mock_window(640, 480, sh_w=640, sh_h=480)
        with patch.object(screen, 'window', return_value=mock_win), \
             patch.object(screen.view, 'setRange'), \
             self._mock_screen():
            screen._fitToVideo()
        mock_win.resize.assert_not_called()

    def test_caps_at_screen_size(self):
        screen = make_screen()
        screen._videoShape = QtCore.QSize(3840, 2160)
        mock_win = self._make_mock_window(640, 480, sh_w=3840, sh_h=2160)
        with patch.object(screen, 'window', return_value=mock_win), \
             self._mock_screen(screen_w=2560, screen_h=1600):
            screen._fitToVideo()
        new_w, new_h = mock_win.resize.call_args[0]
        self.assertLessEqual(new_w, 2560)
        self.assertLessEqual(new_h, 1600)

    def test_caps_at_full_screen_regardless_of_window_position(self):
        # Cap uses the full available screen width, not just room to the right
        # of the current window position — gives consistent results before and
        # after the window has been shown.
        screen = make_screen()
        screen._videoShape = QtCore.QSize(3840, 2160)
        mock_win = self._make_mock_window(640, 480, sh_w=3840, sh_h=2160)
        with patch.object(screen, 'window', return_value=mock_win), \
             self._mock_screen(screen_w=2560, screen_h=1600):
            screen._fitToVideo()
        new_w, new_h = mock_win.resize.call_args[0]
        self.assertLessEqual(new_w, 2560)
        self.assertLessEqual(new_h, 1600)

    def test_maintains_aspect_ratio_when_capping(self):
        screen = make_screen()
        screen._videoShape = QtCore.QSize(3840, 2160)
        mock_win = self._make_mock_window(640, 480, sh_w=3840, sh_h=2160)
        with patch.object(screen, 'window', return_value=mock_win), \
             self._mock_screen(screen_w=2560, screen_h=1600):
            screen._fitToVideo()
        new_w, new_h = mock_win.resize.call_args[0]
        self.assertAlmostEqual(new_w / new_h, 3840 / 2160, places=1)

    def test_accounts_for_window_overhead(self):
        # window sizeHint is 60 px wider/taller than the video (controls overhead)
        screen = make_screen()
        screen._videoShape = QtCore.QSize(1280, 1024)
        mock_win = self._make_mock_window(700, 540, sh_w=1340, sh_h=1084)
        with patch.object(screen, 'window', return_value=mock_win), \
             self._mock_screen():
            screen._fitToVideo()
        mock_win.resize.assert_called_once_with(1340, 1084)

    def test_fit_to_video_calls_window_resize(self):
        screen = make_screen()
        screen._videoShape = QtCore.QSize(1280, 1024)
        mock_win = self._make_mock_window(640, 480, sh_w=1280, sh_h=1024)
        with patch.object(screen, 'window', return_value=mock_win), \
             self._mock_screen():
            screen._fitToVideo()
        mock_win.resize.assert_called_once()

    def test_fit_to_video_sets_range_when_no_resize_needed(self):
        # When window is already the right size, setRange is called directly
        screen = make_screen()
        screen._videoShape = QtCore.QSize(640, 480)
        mock_win = self._make_mock_window(640, 480, sh_w=640, sh_h=480)
        with patch.object(screen, 'window', return_value=mock_win), \
             patch.object(screen.view, 'setRange') as mock_range, \
             self._mock_screen():
            screen._fitToVideo()
        mock_range.assert_called_once_with(
            xRange=(0, 640), yRange=(0, 480), padding=0, update=True)
        mock_win.resize.assert_not_called()

    def test_fit_to_video_does_not_set_range_when_resize_pending(self):
        # When window needs resizing, setRange is deferred to resizeEvent
        screen = make_screen()
        screen._videoShape = QtCore.QSize(1280, 1024)
        mock_win = self._make_mock_window(640, 480, sh_w=1280, sh_h=1024)
        with patch.object(screen, 'window', return_value=mock_win), \
             patch.object(screen.view, 'setRange') as mock_range, \
             self._mock_screen():
            screen._fitToVideo()
        mock_range.assert_not_called()
        mock_win.resize.assert_called_once()

    def test_fit_to_video_sets_minimum_size_within_cap(self):
        # minimum size must not exceed the screen-capped video size
        screen = make_screen()
        screen._videoShape = QtCore.QSize(1280, 1024)
        mock_win = self._make_mock_window(640, 480, sh_w=1280, sh_h=1024)
        with patch.object(screen, 'window', return_value=mock_win), \
             patch.object(screen, 'setMinimumSize') as mock_min, \
             self._mock_screen():
            screen._fitToVideo()
        mock_min.assert_called_once()
        min_w, min_h = mock_min.call_args[0]
        self.assertLessEqual(min_w, 640)
        self.assertLessEqual(min_h, 512)


class TestUpdateShape(unittest.TestCase):

    def test_updateshape_calls_update_geometry(self):
        screen = make_screen()
        shape = QtCore.QSize(640, 480)
        with patch.object(screen, 'updateGeometry') as mock_geom:
            screen.updateShape(shape)
        mock_geom.assert_called_once()

    def test_zero_width_shape_is_ignored(self):
        screen = make_screen()
        screen.updateShape(QtCore.QSize(0, 480))
        self.assertIsNone(screen._videoShape)

    def test_zero_height_shape_is_ignored(self):
        screen = make_screen()
        screen.updateShape(QtCore.QSize(640, 0))
        self.assertIsNone(screen._videoShape)

    def test_zero_zero_shape_is_ignored(self):
        screen = make_screen()
        screen.updateShape(QtCore.QSize(0, 0))
        self.assertIsNone(screen._videoShape)


class TestOverlays(unittest.TestCase):

    def _make_mock_item(self, visible=True):
        item = MagicMock()
        item.isVisible.return_value = visible
        return item

    def test_overlays_empty_on_init(self):
        screen = make_screen()
        self.assertEqual(screen._overlays, [])

    def test_add_overlay_appends_to_list(self):
        screen = make_screen()
        item = self._make_mock_item()
        with patch.object(screen.view, 'addItem'):
            screen.addOverlay(item)
        self.assertIn(item, screen._overlays)

    def test_add_overlay_calls_view_add_item(self):
        screen = make_screen()
        item = self._make_mock_item()
        with patch.object(screen.view, 'addItem') as mock_add:
            screen.addOverlay(item)
        mock_add.assert_called_once_with(item)

    def test_overlays_visible_false_when_none_registered(self):
        screen = make_screen()
        self.assertFalse(screen.overlaysVisible)

    def test_overlays_visible_true_when_any_visible(self):
        screen = make_screen()
        with patch.object(screen.view, 'addItem'):
            screen.addOverlay(self._make_mock_item(visible=False))
            screen.addOverlay(self._make_mock_item(visible=True))
        self.assertTrue(screen.overlaysVisible)

    def test_overlays_visible_false_when_all_hidden(self):
        screen = make_screen()
        with patch.object(screen.view, 'addItem'):
            screen.addOverlay(self._make_mock_item(visible=False))
            screen.addOverlay(self._make_mock_item(visible=False))
        self.assertFalse(screen.overlaysVisible)

    def test_set_overlays_visible_true(self):
        screen = make_screen()
        items = [self._make_mock_item(visible=False) for _ in range(3)]
        with patch.object(screen.view, 'addItem'):
            for item in items:
                screen.addOverlay(item)
        screen.overlaysVisible = True
        for item in items:
            item.setVisible.assert_called_once_with(True)

    def test_set_overlays_visible_false(self):
        screen = make_screen()
        items = [self._make_mock_item(visible=True) for _ in range(3)]
        with patch.object(screen.view, 'addItem'):
            for item in items:
                screen.addOverlay(item)
        screen.overlaysVisible = False
        for item in items:
            item.setVisible.assert_called_once_with(False)

    def test_remove_overlay_removes_from_list(self):
        screen = make_screen()
        item = self._make_mock_item()
        with patch.object(screen.view, 'addItem'):
            screen.addOverlay(item)
        with patch.object(screen.view, 'removeItem'):
            screen.removeOverlay(item)
        self.assertNotIn(item, screen._overlays)

    def test_remove_overlay_calls_view_remove_item(self):
        screen = make_screen()
        item = self._make_mock_item()
        with patch.object(screen.view, 'addItem'):
            screen.addOverlay(item)
        with patch.object(screen.view, 'removeItem') as mock_remove:
            screen.removeOverlay(item)
        mock_remove.assert_called_once_with(item)


class TestFps(unittest.TestCase):

    def test_fps_none_without_source(self):
        screen = make_screen()
        self.assertIsNone(screen.fps)

    def test_fps_returns_source_fps_when_no_throttle(self):
        screen = make_screen()
        source = make_mock_source(fps=60.)
        with patch.object(screen, 'updateShape'):
            screen._source = source
        self.assertEqual(screen.fps, 60.)

    def test_fps_returns_framerate_when_throttled(self):
        screen = make_screen(framerate=30)
        source = make_mock_source(fps=120.)
        with patch.object(screen, 'updateShape'):
            screen._source = source
        self.assertEqual(screen.fps, 30.)

    def test_fps_returns_framerate_without_source_when_throttled(self):
        screen = make_screen(framerate=25)
        self.assertEqual(screen.fps, 25.)


class TestNewFrame(unittest.TestCase):

    def test_setimage_emits_newFrame_when_ready(self):
        screen = make_screen()
        spy = _spy(screen)
        with patch.object(screen.filter, '__call__', return_value=_FRAME):
            with patch.object(screen.image, 'setImage'):
                screen.setImage(_FRAME)
        self.assertEqual(len(spy), 1)

    def test_setimage_does_not_call_render_composite_when_not_composite(self):
        screen = make_screen()
        with patch.object(screen.filter, '__call__', return_value=_FRAME):
            with patch.object(screen.image, 'setImage'):
                with patch.object(screen, '_renderComposite') as mock_render:
                    screen.setImage(_FRAME)
        mock_render.assert_not_called()

    def test_setimage_calls_render_composite_when_composite_true(self):
        screen = make_screen()
        screen._composite = True
        with patch.object(screen.filter, '__call__', return_value=_FRAME):
            with patch.object(screen.image, 'setImage'):
                with patch.object(screen, '_renderComposite', return_value=_FRAME) as mock_render:
                    screen.setImage(_FRAME)
        mock_render.assert_called_once()

    def test_setimage_does_not_emit_newFrame_when_not_ready(self):
        screen = make_screen()
        screen._ready = False
        spy = _spy(screen)
        screen.setImage(_FRAME)
        self.assertEqual(len(spy), 0)


class TestColormap(unittest.TestCase):

    def test_colormap_none_on_init(self):
        screen = make_screen()
        self.assertIsNone(screen._colormap)

    def test_colormap_getter_returns_stored(self):
        screen = make_screen()
        screen._colormap = 'inferno'
        self.assertEqual(screen.colormap, 'inferno')

    def test_colormap_setter_none_stores_none(self):
        screen = make_screen()
        screen._colormap = 'inferno'
        with patch.object(screen.image, 'setLookupTable'):
            screen.colormap = None
        self.assertIsNone(screen._colormap)

    def test_colormap_setter_none_calls_set_lookup_table(self):
        screen = make_screen()
        with patch.object(screen.image, 'setLookupTable') as mock_lut:
            screen.colormap = None
        mock_lut.assert_called_once_with(None)

    def test_colormap_setter_stores_name(self):
        screen = make_screen()
        mock_cm = MagicMock()
        with patch('pyqtgraph.colormap.get',
                   return_value=mock_cm), \
             patch.object(screen.image, 'setColorMap'):
            screen.colormap = 'viridis'
        self.assertEqual(screen._colormap, 'viridis')

    def test_colormap_setter_calls_set_color_map(self):
        screen = make_screen()
        mock_cm = MagicMock()
        with patch('pyqtgraph.colormap.get',
                   return_value=mock_cm), \
             patch.object(screen.image, 'setColorMap') as mock_set:
            screen.colormap = 'inferno'
        mock_set.assert_called_once_with(mock_cm)

    def test_colormap_setter_falls_back_to_builtin(self):
        screen = make_screen()
        mock_cm = MagicMock()

        def _get(name, source=None):
            if source == 'matplotlib':
                raise ImportError('no matplotlib')
            return mock_cm

        with patch('pyqtgraph.colormap.get',
                   side_effect=_get), \
             patch.object(screen.image, 'setColorMap') as mock_set:
            screen.colormap = 'thermal'
        mock_set.assert_called_once_with(mock_cm)

    def test_colormap_setter_invalid_raises(self):
        screen = make_screen()
        with patch('pyqtgraph.colormap.get',
                   side_effect=KeyError('no such colormap')):
            with self.assertRaises(KeyError):
                screen.colormap = 'nonexistent_map'


class TestComposite(unittest.TestCase):

    def test_composite_false_on_init(self):
        screen = make_screen()
        self.assertFalse(screen._composite)

    def test_composite_getter(self):
        screen = make_screen()
        screen._composite = True
        self.assertTrue(screen.composite)

    def test_composite_setter(self):
        screen = make_screen()
        screen.composite = True
        self.assertTrue(screen._composite)

    def test_composite_setter_false(self):
        screen = make_screen()
        screen.composite = True
        screen.composite = False
        self.assertFalse(screen._composite)


if __name__ == '__main__':
    unittest.main()
