'''Unit tests for the viva-genicam camera, on the fake devices of the
package.'''
import sys
import unittest
from unittest.mock import MagicMock, patch
from qtpy import QtWidgets
from QVideo.lib.errors import QDeviceError

try:
    import viva_genicam as vg
    from viva_genicam.testing import FakeU3vCamera
    from QVideo.cameras.Viva import QVivaCamera, QVivaTree
except ImportError:  # pragma: no cover
    vg = None

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

MODULE = sys.modules.get('QVideo.cameras.Viva._camera')


class FakeCamera(QVivaCamera if vg else object):

    '''A camera that connects to a fake device.'''

    def _connect(self):
        return FakeU3vCamera(width=640, height=480).connect()


class Locking:

    '''A device that refuses integer writes while it streams, as a camera
    does for the frame size.'''

    def __init__(self, device):
        self._device = device
        self.streaming = False

    def __getattr__(self, name):
        return getattr(self._device, name)

    def set_integer(self, name, value):
        if self.streaming:
            raise vg.GenApiError(f'{name} is locked while streaming')
        self._device.set_integer(name, value)

    def stream(self):
        stream, device = self._device.stream(), self
        enter, leave = stream.__enter__, stream.__exit__

        class Tracked:
            def __enter__(self):
                device.streaming = True
                return enter()

            def __exit__(self, *args):
                device.streaming = False
                return leave(*args)

            def __getattr__(self, name):
                return getattr(stream, name)
        return Tracked()


class LockingCamera(FakeCamera):

    def _connect(self):
        return Locking(super()._connect())


class Readonly:

    '''A device that reports the features in *names* as read-only, as a
    camera does for the exposure time while the exposure is automatic.'''

    def __init__(self, device, names=()):
        self._device = device
        self.names = set(names)

    def __getattr__(self, name):
        return getattr(self._device, name)

    def feature_state(self, name):
        state = self._device.feature_state(name)
        if name not in self.names:
            return state

        class Locked:
            access = 'RO'

            def __getattr__(self, attribute):
                return getattr(state, attribute)
        return Locked()


class AccessCamera(FakeCamera):

    #: The features that the device reports as read-only at first.
    readonly = ()

    def _connect(self):
        return Readonly(super()._connect(), self.readonly)


def device_info(speed: str | None, transport: str = 'u3v') -> MagicMock:
    info = MagicMock()
    info.transport, info.speed, info.model = transport, speed, 'Blackfly'
    return info


@unittest.skipIf(vg is None, 'viva-genicam is not installed')
class TestOpen(unittest.TestCase):

    def test_features_become_properties_and_commands_methods(self):
        with FakeCamera() as camera:
            self.assertIn('Width', camera.properties)
            self.assertIn('PixelFormat', camera.properties)
            self.assertIn('AcquisitionStart', camera.methods)
            self.assertNotIn('AcquisitionStart', camera.properties)

    def test_an_enumeration_lists_its_entries(self):
        with FakeCamera() as camera:
            spec = camera.properties['PixelFormat']
            self.assertIn('Mono8', spec['limits'])

    def test_a_number_carries_its_limits(self):
        with FakeCamera() as camera:
            spec = camera.properties['Width']
            self.assertEqual((spec['minimum'], spec['maximum']), (1, 4096))

    def test_the_standard_names_are_aliases(self):
        with FakeCamera() as camera:
            self.assertEqual(camera.width, 640)
            self.assertEqual(camera.height, 480)
            self.assertEqual(camera.aliases['fps'], 'AcquisitionFrameRate')

    def test_the_model_name_is_the_one_the_camera_reports(self):
        with FakeCamera() as camera:
            self.assertEqual(camera.model_name, 'FakeU3V')

    def test_a_missing_camera_is_reported(self):
        with patch.object(MODULE.vg, 'discover_u3v', return_value=[]), \
                patch.object(MODULE.vg, 'discover', return_value=[]):
            with self.assertRaises(QDeviceError):
                QVivaCamera()

    def test_the_gige_search_waits_until_usb_has_none_left(self):
        with patch.object(MODULE.vg, 'discover_u3v',
                          return_value=[device_info('super speed')]), \
                patch.object(MODULE.vg, 'discover') as discover, \
                patch.object(MODULE.vg, 'connect_u3v',
                             return_value=FakeU3vCamera().connect()):
            QVivaCamera(cameraID=0).close()
        discover.assert_not_called()

    def test_a_failed_open_releases_the_device(self):
        camera = FakeCamera.__new__(FakeCamera)
        with patch.object(FakeCamera, '_startStream',
                          side_effect=RuntimeError('no stream')):
            with self.assertRaises(RuntimeError):
                FakeCamera.__init__(camera)
        self.assertIsNone(camera._device)
        with FakeCamera() as again:  # nothing stays claimed
            self.assertTrue(again.isOpen())


@unittest.skipIf(vg is None, 'viva-genicam is not installed')
class NoClock:

    '''A device whose clock cannot be calibrated.'''

    def __init__(self, device, transport):
        self._device = device
        self.transport = transport

    def __getattr__(self, name):
        return getattr(self._device, name)

    def time_calibrate(self, *args, **kwargs):
        raise vg.GenicamError('no timestamp counter')


class TestClock(unittest.TestCase):

    def camera(self, transport):
        class Camera(FakeCamera):
            def _connect(self):
                return NoClock(super()._connect(), transport)

        return Camera()

    def test_a_gige_clock_that_cannot_be_calibrated_is_reported(self):
        with self.assertLogs('QVideo.cameras.Viva._camera',
                             'WARNING') as logs:
            camera = self.camera('gige')
        self.addCleanup(camera.close)
        self.assertTrue(camera.isOpen())
        self.assertIn('clock of the camera', logs.output[0])

    def test_a_usb_camera_has_no_clock_to_calibrate_and_no_warning(self):
        with self.assertNoLogs('QVideo.cameras.Viva._camera', 'WARNING'):
            with self.camera('u3v'):
                pass

    def test_the_fake_usb_camera_is_not_reported(self):
        with self.assertNoLogs('QVideo.cameras.Viva._camera', 'WARNING'):
            with FakeCamera():
                pass


class TestTimestamp(unittest.TestCase):

    def frame(self, host=None, device=None):
        return MagicMock(ts_host=host, ts_dev=device)

    def test_the_time_of_the_host_is_used_when_the_clock_is_calibrated(self):
        stamp = QVivaCamera._timestamp(self.frame(1.7e9, 123))
        self.assertEqual(stamp, 1.7e9)

    def test_the_ticks_of_the_camera_are_nanoseconds(self):
        stamp = QVivaCamera._timestamp(self.frame(None, 2_500_000_000))
        self.assertAlmostEqual(stamp, 2.5)

    def test_a_frame_without_a_timestamp_has_none(self):
        self.assertIsNone(QVivaCamera._timestamp(self.frame()))
        self.assertIsNone(QVivaCamera._timestamp(self.frame(None, 0)))

    def test_a_frame_read_from_a_usb_camera_has_the_time_of_the_camera(self):
        with FakeCamera() as camera:
            stamps = []
            for _ in range(5):
                ok, _frame = camera.saferead()
                stamps.append(camera.hardwareTimestamp)
        self.assertTrue(ok)
        self.assertNotIn(None, stamps)
        self.assertEqual(stamps, sorted(set(stamps)))   # it runs forward


class TestUsbLink(unittest.TestCase):

    def check(self, speed):
        camera = FakeCamera.__new__(FakeCamera)
        with self.assertLogs(MODULE.logger, 'WARNING') as logs:
            QVivaCamera._checkLink(camera, device_info(speed))
        return logs.output[0]

    def test_a_slow_link_is_reported(self):
        for speed in ('high speed (480 Mbit/s, USB 2)', 'full speed'):
            message = self.check(speed)
            self.assertIn(speed, message)
            self.assertIn('USB 3', message)

    def test_a_fast_link_is_not_reported(self):
        camera = FakeCamera.__new__(FakeCamera)
        with self.assertNoLogs(MODULE.logger, 'WARNING'):
            QVivaCamera._checkLink(
                camera, device_info('super speed (5000 Mbit/s, USB 3)'))
            QVivaCamera._checkLink(camera, device_info(None))


@unittest.skipIf(vg is None, 'viva-genicam is not installed')
class TestRead(unittest.TestCase):

    def test_a_timeout_is_a_failed_read(self):
        with FakeCamera() as camera:
            camera._stream = MagicMock()
            camera._stream.next_frame.side_effect = vg.TransportError(
                'timeout waiting for frame')
            with self.assertLogs(MODULE.logger, 'WARNING'):
                self.assertEqual(camera.read(), (False, None))

    def test_a_clean_end_of_the_stream_is_a_failed_read(self):
        with FakeCamera() as camera:
            camera._stream = MagicMock()
            camera._stream.next_frame.return_value = None
            self.assertEqual(camera.read(), (False, None))

    def test_a_frame_arrives_as_an_array(self):
        with FakeCamera() as camera:
            ok, frame = camera.read()
            self.assertTrue(ok)
            self.assertEqual(frame.shape, (480, 640))


@unittest.skipIf(vg is None, 'viva-genicam is not installed')
class TestWrite(unittest.TestCase):

    def test_a_feature_locked_by_the_stream_is_written_stopped(self):
        with LockingCamera() as camera:
            first = camera._stream
            camera.set('Width', 320)
            self.assertIsNot(camera._stream, first)
            self.assertEqual(camera.width, 320)

    def test_a_read_only_feature_is_not_restarted_for(self):
        with FakeCamera() as camera:
            stream = camera._stream
            camera.set('DeviceModelName', 'x')
            self.assertIs(camera._stream, stream)

    def test_a_new_frame_size_is_announced(self):
        with FakeCamera() as camera:
            shapes = []
            camera.shapeChanged.connect(shapes.append)
            camera.set('Width', 320)
            self.assertEqual(len(shapes), 1)


@unittest.skipIf(vg is None, 'viva-genicam is not installed')
class TestLevels(unittest.TestCase):

    def test_an_8_bit_format_has_no_levels(self):
        with FakeCamera() as camera:
            self.assertIsNone(camera.levels)

    def test_a_12_bit_format_has_levels_that_follow_the_setting(self):
        with FakeCamera() as camera:
            camera.set('PixelFormat', 'Mono12Packed')
            self.assertEqual(camera.levels, (0, 4095))
            camera.set('PixelFormat', 'Mono8')
            self.assertIsNone(camera.levels)

    def test_the_levels_of_each_format(self):
        levels = {'Mono8': None, 'Mono10': (0, 1023), 'Mono12p': (0, 4095),
                  'Mono14': (0, 16383), 'Mono16': None, 'BayerRG12': (0, 4095),
                  'RGB8Packed': None, None: None}
        for name, want in levels.items():
            with self.subTest(name=name):
                self.assertEqual(MODULE._pixelLevels(name), want)


@unittest.skipIf(vg is None, 'viva-genicam is not installed')
class TestTree(unittest.TestCase):

    def test_the_tree_shows_the_curated_controls_the_camera_has(self):
        camera = FakeCamera()
        tree = QVivaTree(camera=camera)
        try:
            names = set(tree._parameters)
            self.assertIn('Width', names)
            self.assertNotIn('DeviceModelName', names)
        finally:
            tree.stop()
            camera.close()


@unittest.skipIf(vg is None, 'viva-genicam is not installed')
class TestAccess(unittest.TestCase):

    '''A feature is writable exactly when it has a setter.'''

    def test_a_feature_that_becomes_read_only_loses_its_setter(self):
        with AccessCamera() as camera:
            self.assertIsNotNone(camera.properties['Height']['setter'])
            camera._device.names.add('Height')
            camera.updateAccess()
            self.assertIsNone(camera.properties['Height']['setter'])

    def test_a_feature_that_becomes_writable_gets_a_setter(self):
        class Locked(AccessCamera):
            readonly = ('Height',)

        with Locked() as camera:
            self.assertIsNone(camera.properties['Height']['setter'])
            camera._device.names.clear()
            camera.updateAccess()
            self.assertIsNotNone(camera.properties['Height']['setter'])
            camera.set('Height', 240)  # and it works
            self.assertEqual(camera.height, 240)

    def test_a_feature_locked_by_the_stream_keeps_its_setter(self):
        with AccessCamera() as camera:
            camera._streamLocked.add('Height')
            camera._device.names.add('Height')
            camera.updateAccess()
            self.assertIsNotNone(camera.properties['Height']['setter'])

    def test_the_tree_follows_the_camera(self):
        with AccessCamera() as camera:
            tree = QVivaTree(camera=camera, controls=['Height', 'Width'])
            try:
                self.assertTrue(tree._parameters['Height'].opts['enabled'])
                camera._device.names.add('Height')
                tree._sync(None, [])
                self.assertFalse(tree._parameters['Height'].opts['enabled'])
                self.assertTrue(tree._parameters['Width'].opts['enabled'])
                camera._device.names.clear()
                tree._sync(None, [])
                self.assertTrue(tree._parameters['Height'].opts['enabled'])
            finally:
                tree.stop()

    def test_a_tree_opened_on_a_locked_control_enables_it_later(self):
        class Locked(AccessCamera):
            readonly = ('Height',)

        with Locked() as camera:
            tree = QVivaTree(camera=camera, controls=['Height', 'Width'])
            try:
                self.assertFalse(tree._parameters['Height'].opts['enabled'])
                camera._device.names.clear()
                tree._sync(None, [])
                self.assertTrue(tree._parameters['Height'].opts['enabled'])
            finally:
                tree.stop()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
