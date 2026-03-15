'''Unit tests for QNoiseCamera and QNoiseSource.'''
import unittest
import numpy as np
from unittest.mock import patch
from pyqtgraph.Qt import QtWidgets, QtTest
from QVideo.cameras.Noise.QNoiseCamera import QNoiseCamera, QNoiseSource


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_camera(**kwargs) -> QNoiseCamera:
    '''Return a QNoiseCamera with time.sleep suppressed.'''
    return QNoiseCamera(**kwargs)


class TestInit(unittest.TestCase):

    def test_opens_on_init(self):
        cam = make_camera()
        self.assertTrue(cam.isOpen())

    def test_default_width(self):
        cam = make_camera()
        self.assertEqual(cam.width, 640)

    def test_default_height(self):
        cam = make_camera()
        self.assertEqual(cam.height, 480)

    def test_default_fps(self):
        cam = make_camera()
        self.assertAlmostEqual(cam.fps, 30.)

    def test_default_blacklevel(self):
        cam = make_camera()
        self.assertEqual(cam.blacklevel, 0)

    def test_default_whitelevel(self):
        cam = make_camera()
        self.assertEqual(cam.whitelevel, 255)

    def test_custom_blacklevel(self):
        cam = make_camera(blacklevel=48)
        self.assertEqual(cam.blacklevel, 48)

    def test_custom_whitelevel(self):
        cam = make_camera(whitelevel=200)
        self.assertEqual(cam.whitelevel, 200)

    def test_blacklevel_clamped_below(self):
        cam = make_camera(blacklevel=-10)
        self.assertEqual(cam.blacklevel, 0)

    def test_blacklevel_clamped_above(self):
        cam = make_camera(blacklevel=300)
        self.assertEqual(cam.blacklevel, 254)

    def test_whitelevel_clamped_below(self):
        cam = make_camera(whitelevel=0)
        self.assertEqual(cam.whitelevel, 1)

    def test_whitelevel_clamped_above(self):
        cam = make_camera(whitelevel=300)
        self.assertEqual(cam.whitelevel, 255)

    def test_all_properties_registered(self):
        cam = make_camera()
        for name in ('width', 'height', 'fps', 'color',
                     'blacklevel', 'whitelevel'):
            self.assertIn(name, cam.properties)

    def test_name_is_class_name(self):
        cam = make_camera()
        self.assertEqual(cam.name, 'QNoiseCamera')


class TestInitialize(unittest.TestCase):

    def test_rng_created_on_open(self):
        cam = make_camera()
        self.assertIsNotNone(cam._rng)

    def test_rng_is_generator(self):
        cam = make_camera()
        self.assertIsInstance(cam._rng, np.random.Generator)


class TestDeinitialize(unittest.TestCase):

    def test_rng_cleared_on_close(self):
        cam = make_camera()
        cam.close()
        self.assertIsNone(cam._rng)

    def test_isopen_false_after_close(self):
        cam = make_camera()
        cam.close()
        self.assertFalse(cam.isOpen())

    def test_close_is_idempotent(self):
        cam = make_camera()
        cam.close()
        try:
            cam.close()
        except Exception as e:
            self.fail(f'Second close() raised {e}')


class TestProperties(unittest.TestCase):

    def test_width_setter(self):
        cam = make_camera()
        cam.set('width', 320)
        self.assertEqual(cam.width, 320)

    def test_height_setter(self):
        cam = make_camera()
        cam.set('height', 240)
        self.assertEqual(cam.height, 240)

    def test_fps_setter(self):
        cam = make_camera()
        cam.set('fps', 60.)
        self.assertAlmostEqual(cam.fps, 60.)

    def test_color_is_always_false(self):
        cam = make_camera()
        self.assertFalse(cam.color)

    def test_color_is_read_only(self):
        cam = make_camera()
        with self.assertLogs('QVideo.lib.QCamera', level='WARNING'):
            cam.set('color', True)

    def test_blacklevel_setter(self):
        cam = make_camera()
        cam.set('blacklevel', 32)
        self.assertEqual(cam.blacklevel, 32)

    def test_whitelevel_setter(self):
        cam = make_camera()
        cam.set('whitelevel', 200)
        self.assertEqual(cam.whitelevel, 200)

    def test_blacklevel_setter_clamps_below(self):
        cam = make_camera()
        cam.set('blacklevel', -5)
        self.assertEqual(cam.blacklevel, 0)

    def test_blacklevel_setter_clamps_above(self):
        cam = make_camera()
        cam.set('blacklevel', 300)
        self.assertEqual(cam.blacklevel, 254)

    def test_whitelevel_setter_clamps_below(self):
        cam = make_camera()
        cam.set('whitelevel', 0)
        self.assertEqual(cam.whitelevel, 1)

    def test_whitelevel_setter_clamps_above(self):
        cam = make_camera()
        cam.set('whitelevel', 300)
        self.assertEqual(cam.whitelevel, 255)

    def test_width_setter_emits_shape_changed(self):
        cam = make_camera()
        spy = QtTest.QSignalSpy(cam.shapeChanged)
        cam.set('width', 320)
        self.assertEqual(len(spy), 1)

    def test_height_setter_emits_shape_changed(self):
        cam = make_camera()
        spy = QtTest.QSignalSpy(cam.shapeChanged)
        cam.set('height', 240)
        self.assertEqual(len(spy), 1)


class TestRead(unittest.TestCase):

    def test_read_returns_true(self):
        cam = make_camera()
        with patch('time.sleep'):
            ok, _ = cam.read()
        self.assertTrue(ok)

    def test_read_returns_ndarray(self):
        cam = make_camera()
        with patch('time.sleep'):
            _, frame = cam.read()
        self.assertIsInstance(frame, np.ndarray)

    def test_frame_dtype_is_uint8(self):
        cam = make_camera()
        with patch('time.sleep'):
            _, frame = cam.read()
        self.assertEqual(frame.dtype, np.uint8)

    def test_frame_shape_matches_height_width(self):
        cam = make_camera()
        with patch('time.sleep'):
            _, frame = cam.read()
        self.assertEqual(frame.shape, (cam.height, cam.width))

    def test_frame_shape_after_resize(self):
        cam = make_camera()
        cam.set('width', 320)
        cam.set('height', 240)
        with patch('time.sleep'):
            _, frame = cam.read()
        self.assertEqual(frame.shape, (240, 320))

    def test_pixel_values_in_range(self):
        cam = make_camera(blacklevel=50, whitelevel=150)
        with patch('time.sleep'):
            _, frame = cam.read()
        self.assertGreaterEqual(int(frame.min()), 50)
        self.assertLess(int(frame.max()), 150)

    def test_read_sleeps_for_fps_interval(self):
        cam = make_camera()
        with patch('time.sleep') as mock_sleep:
            cam.read()
        mock_sleep.assert_called_once_with(1. / cam.fps)


class TestQNoiseSource(unittest.TestCase):

    def test_creates_camera_when_none_given(self):
        src = QNoiseSource()
        self.assertIsInstance(src.source, QNoiseCamera)

    def test_uses_provided_camera(self):
        cam = make_camera()
        src = QNoiseSource(camera=cam)
        self.assertIs(src.source, cam)

    def test_kwargs_forwarded_to_camera(self):
        src = QNoiseSource(blacklevel=48, whitelevel=200)
        self.assertEqual(src.source.blacklevel, 48)
        self.assertEqual(src.source.whitelevel, 200)


if __name__ == '__main__':
    unittest.main()
