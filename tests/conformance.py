'''Conformance checks that every camera backend must pass.

A backend adopts the suite by mixing :class:`CameraConformance` into a
``unittest.TestCase`` and saying how to make one of its cameras::

    class TestMyCameraConforms(CameraConformance, unittest.TestCase):
        def makeCamera(self):
            return MyCamera(...)

The checks state the contract that the rest of QVideo relies on: the
lifecycle can be repeated, frames are independent arrays that agree with
the reported shape, properties are typed and survive a round trip, the
device lock lets frames and settings interleave, and a source can stream
the camera and stop.  They need no hardware when ``makeCamera`` returns a
simulated device.
'''
import threading
import numpy as np
from qtpy import QtWidgets
from QVideo.lib import QVideoSource
from QVideo.tests.fakes import until
from QVideo.tests.signals import record

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

FRAME_DTYPES = (np.uint8, np.uint16)


def readFrames(camera, n):
    '''Return *n* frames from an open *camera*.'''
    frames = []
    for _ in range(n):
        ok, frame = camera.read()
        assert ok, f'{camera.name} could not read frame {len(frames)}'
        frames.append(frame)
    return frames


class CameraConformance:

    '''Checks for a ``unittest.TestCase`` that defines :meth:`makeCamera`.'''

    def makeCamera(self):
        '''Return a camera of the backend under test.'''
        raise NotImplementedError

    def setUp(self):
        self.camera = self.makeCamera().open()
        self.addCleanup(self.camera.close)

    def writable(self):
        '''Names of the properties that can be written.'''
        properties = self.camera._properties
        return [name for name in self.camera.properties
                if properties[name]['setter'] is not None]

    # -- lifecycle ---------------------------------------------------

    def test_open_returns_the_camera_and_may_be_repeated(self):
        self.assertTrue(self.camera.isOpen())
        self.assertIs(self.camera.open(), self.camera)
        self.assertTrue(self.camera.isOpen())

    def test_close_may_be_repeated(self):
        self.camera.close()
        self.camera.close()
        self.assertFalse(self.camera.isOpen())

    def test_the_camera_reads_again_after_it_is_reopened(self):
        self.camera.close()
        self.camera.open()
        self.assertTrue(self.camera.read()[0])

    def test_the_context_manager_opens_and_closes(self):
        self.camera.close()
        with self.camera as camera:
            self.assertTrue(camera.isOpen())
        self.assertFalse(self.camera.isOpen())

    # -- frames ------------------------------------------------------

    def test_a_frame_is_an_array_of_a_supported_kind(self):
        ok, frame = self.camera.read()
        self.assertTrue(ok)
        self.assertIsInstance(frame, np.ndarray)
        self.assertIn(frame.ndim, (2, 3))
        self.assertIn(frame.dtype.type, FRAME_DTYPES)

    def test_a_frame_agrees_with_the_reported_shape(self):
        _, frame = self.camera.read()
        shape = self.camera.shape
        self.assertEqual(frame.shape[:2], (shape.height(), shape.width()))

    def test_the_shape_is_stable_while_frames_are_read(self):
        shape = self.camera.shape
        for frame in readFrames(self.camera, 5):
            self.assertEqual(frame.shape[:2], (shape.height(), shape.width()))
        self.assertEqual(self.camera.shape, shape)

    def test_frames_do_not_share_memory(self):
        first, second = readFrames(self.camera, 2)
        self.assertFalse(np.shares_memory(first, second))

    def test_a_frame_survives_the_next_read(self):
        first, = readFrames(self.camera, 1)
        kept = first.copy()
        readFrames(self.camera, 3)
        np.testing.assert_array_equal(first, kept)

    def test_the_hardware_timestamp_is_none_or_a_number(self):
        self.camera.read()
        stamp = self.camera.hardwareTimestamp
        self.assertTrue(stamp is None or isinstance(stamp, float))

    # -- properties --------------------------------------------------

    def test_every_property_reads_as_its_declared_type(self):
        for name in self.camera.properties:
            with self.subTest(name):
                ptype = self.camera._properties[name]['ptype']
                value = self.camera.get(name)
                if value is None:  # not readable at the moment
                    continue
                if ptype is float:
                    ptype = (int, float)
                self.assertIsInstance(value, ptype)

    def test_the_settings_name_only_properties(self):
        # A backend may leave out aliases, such as width for Width.
        self.assertLessEqual(set(self.camera.settings),
                             set(self.camera.properties))

    def test_the_settings_can_be_applied_again(self):
        settings = self.camera.settings
        self.camera.settings = settings
        for name, value in settings.items():
            if isinstance(value, float):
                self.assertAlmostEqual(self.camera.get(name), value,
                                       delta=1e-6 + 1e-6 * abs(value))
            elif value is not None:
                self.assertEqual(self.camera.get(name), value)

    def test_a_property_keeps_its_value_when_set_to_it(self):
        for name in self.writable():
            with self.subTest(name):
                before = self.camera.get(name)
                if before is None:
                    continue
                self.camera.set(name, before)
                after = self.camera.get(name)
                if isinstance(before, float):
                    self.assertAlmostEqual(after, before, delta=1e-6 +
                                           1e-6 * abs(before))
                else:
                    self.assertEqual(after, before)

    def test_a_read_only_property_refuses_a_write_quietly(self):
        properties = self.camera._properties
        names = [n for n in self.camera.properties
                 if properties[n]['setter'] is None]
        if not names:
            self.skipTest('the camera has no read-only property')
        for name in names:
            with self.subTest(name):
                before = self.camera.get(name)
                with self.assertLogs(level='WARNING'):
                    self.camera.set(name, before)
                self.assertEqual(self.camera.get(name), before)

    def test_unknown_names_are_reported_not_raised(self):
        with self.assertLogs(level='ERROR'):
            self.camera.set('no-such-property', 1)
        self.assertIsNone(self.camera.get('no-such-property'))
        with self.assertLogs(level='ERROR'):
            self.camera.execute('no-such-method')

    def test_the_names_are_strings(self):
        self.assertIsInstance(self.camera.name, str)
        self.assertIsInstance(self.camera.model_name, (str, type(None)))

    # -- the device lock ---------------------------------------------

    def test_settings_may_change_while_frames_are_read(self):
        names = self.writable()
        if not names:
            self.skipTest('the camera has no writable property')
        errors = []

        def reader():
            try:
                readFrames(self.camera, 20)
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=reader)
        thread.start()
        while thread.is_alive():
            for name in names:
                value = self.camera.get(name)
                if value is not None:
                    self.camera.set(name, value)
            thread.join(0.01)
        thread.join(10)
        self.assertFalse(thread.is_alive(), 'the reader is stuck')
        self.assertEqual(errors, [])

    # -- streaming ---------------------------------------------------

    def test_a_source_streams_frames_in_order_and_stops(self):
        source = QVideoSource(self.camera)
        frames = record(source.newFrame)
        source.start()
        self.addCleanup(source.wait)
        self.addCleanup(source.stop)
        self.assertTrue(until(lambda: len(frames) >= 5, 10000))
        source.stop()
        source.wait()
        self.assertFalse(source.isRunning())
        indices = [args[1].index for args in frames]
        self.assertEqual(indices, sorted(indices))
        self.assertEqual(indices[0], 0)
        stamps = [args[1].timestamp for args in frames]
        self.assertEqual(stamps, sorted(stamps))

    def test_a_camera_that_a_source_closed_opens_again(self):
        source = QVideoSource(self.camera)
        frames = record(source.newFrame)
        source.start()
        until(lambda: len(frames) >= 2, 10000)
        source.stop()
        source.wait()
        self.assertFalse(self.camera.isOpen())  # the source owns the device
        self.camera.open()
        self.assertTrue(self.camera.read()[0])
