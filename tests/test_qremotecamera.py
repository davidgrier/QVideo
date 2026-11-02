'''Unit tests for QRemoteCamera: a camera in a process of its own.'''
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
import unittest
import unittest.mock

from multiprocessing.connection import Connection

import numpy as np
from qtpy import QtWidgets

from QVideo.lib import QCameraError, QCameraTree, QVideoSource
from QVideo.lib._remote import EVENT, REPLY
from QVideo.lib.QRemoteCamera import QRemoteCamera
from QVideo.tests.signals import record

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

LOGGER = 'QVideo.lib.QRemoteCamera'
FAILING = 'QVideo.tests.remotecameras:FailingCamera'
FLOATING = 'QVideo.tests.remotecameras:FloatCamera'
STATES = 'QVideo.tests.remotecameras:StatesCamera'
SHRINKING = 'QVideo.tests.remotecameras:ShrinkingCamera'

# A camera in a process of its own needs file descriptors to pass to the
# worker, which Windows does not have.
not_on_windows = unittest.skipIf(sys.platform == 'win32',
                                 'not available on Windows yet')


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)],
                          capture_output=True, text=True
                          ).stdout.strip().startswith(('R', 'S', 'U', 'I'))


def wait_for(condition, seconds=10.) -> bool:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        if condition():
            return True
        app.processEvents()
        time.sleep(0.02)
    return False


@not_on_windows
class TestRemoteCamera(unittest.TestCase):

    def setUp(self):
        self.camera = QRemoteCamera('noise')
        self.addCleanup(self.camera.close)

    def test_mirrors_the_camera(self):
        self.assertTrue(self.camera.isOpen())
        self.assertEqual(self.camera.name, 'QNoiseCamera')
        self.assertEqual(set(self.camera.properties),
                         {'width', 'height', 'fps', 'color', 'blacklevel',
                          'whitelevel'})
        self.assertEqual(self.camera.width, 640)
        self.assertEqual(self.camera.shape.height(), 480)

    def test_read_only_stays_read_only(self):
        self.assertIsNone(self.camera.properties['color']['setter'])

    def test_settings_in_one_request(self):
        self.assertEqual(self.camera.settings['fps'], 30.)
        self.camera.settings = {'blacklevel': 10, 'whitelevel': 20}
        self.assertEqual(self.camera.blacklevel, 10)

    def test_reads_frames(self):
        self.camera.settings = {'blacklevel': 10, 'whitelevel': 20}
        ok, frame = False, None
        for _ in range(10):
            ok, frame = self.camera.saferead()
            if ok and frame.max() < 20:
                break
        self.assertTrue(ok)
        self.assertEqual(frame.shape, (480, 640))
        self.assertEqual(frame.dtype, np.uint8)
        self.assertLess(frame.max(), 20)

    def test_frame_is_a_copy(self):
        ok, first = self.camera.saferead()
        self.assertTrue(ok)
        before = first.copy()
        for _ in range(10):
            self.camera.saferead()
        np.testing.assert_array_equal(first, before)

    def test_new_shape_is_announced_and_delivered(self):
        spy = record(self.camera.shapeChanged)
        self.camera.width = 320
        self.assertEqual(len(spy), 1)
        self.assertEqual((spy[0][0].width(), spy[0][0].height()),
                         (320, 480))
        shape = None
        for _ in range(20):
            ok, frame = self.camera.saferead()
            if ok and frame.shape[1] == 320:
                shape = frame.shape
                break
        self.assertEqual(shape, (480, 320))
        for _ in range(5):
            self.camera.saferead()
        self.assertEqual(len(spy), 1)       # frames do not announce shapes

    def test_larger_frames_get_a_new_ring(self):
        self.camera.width = 1000
        self.camera.height = 800
        shape = None
        for _ in range(30):
            ok, frame = self.camera.saferead()
            if ok and frame.shape == (800, 1000):
                shape = frame.shape
                break
        self.assertEqual(shape, (800, 1000))

    def test_it_opens_again_with_a_new_worker(self):
        first = self.camera._process.pid
        self.assertTrue(self.camera.saferead()[0])  # it has a ring to forget
        self.camera.close()
        self.camera.open()
        self.assertTrue(self.camera.isOpen())
        self.assertNotEqual(self.camera._process.pid, first)
        ok = False
        for _ in range(10):
            ok, frame = self.camera.saferead()
            if ok:
                break
        self.assertTrue(ok)
        self.assertEqual(frame.shape, (480, 640))

    def test_unknown_request_is_reported(self):
        with self.assertRaises(QCameraError):
            self.camera._call('nothing')

    def test_close_ends_the_worker(self):
        pid = self.camera._process.pid
        self.camera.close()
        self.assertFalse(self.camera.isOpen())
        self.assertTrue(wait_for(lambda: not alive(pid)))

    def test_a_dead_worker_is_an_error_not_a_hang(self):
        self.camera._process.kill()
        self.camera._process.wait()
        with self.assertRaises(QCameraError):
            self.camera.get('fps')
        ok, frame = self.camera.saferead()
        self.assertFalse(ok)
        self.assertTrue(wait_for(lambda: self.camera._lost))


@unittest.skipUnless(os.environ.get('QVIDEO_TEST_HARDWARE'),
                     'set QVIDEO_TEST_HARDWARE=1 to use the laptop camera')
@not_on_windows
class TestOpenCVHardware(unittest.TestCase):

    def test_color_frames_and_resolutions(self):
        camera = QRemoteCamera('opencv')
        original = camera.resolution
        try:
            ok, frame = False, None
            for _ in range(60):
                ok, frame = camera.saferead()
                if ok:
                    break
            self.assertTrue(ok)
            self.assertEqual(frame.ndim, 3)
            self.assertEqual(frame.shape[2], 3)
            small = camera.properties['resolution']['limits'][0]
            spy = record(camera.shapeChanged)
            camera.resolution = small
            self.assertEqual(len(spy), 1)
            w, h = camera.shape.width(), camera.shape.height()
            for _ in range(60):
                ok, frame = camera.saferead()
                if ok and frame.shape[:2] == (h, w):
                    break
            self.assertEqual(frame.shape, (h, w, 3))
            self.assertEqual(len(spy), 1)
        finally:
            camera.resolution = original
            camera.close()


@not_on_windows
class TestWithTheSourceAndTheTree(unittest.TestCase):

    def test_source_delivers_frames(self):
        camera = QRemoteCamera('noise')
        source = QVideoSource(camera)
        spy = record(source.newFrame)
        source.start()
        try:
            self.assertTrue(wait_for(lambda: len(spy) >= 3))
        finally:
            source.stop()
            source.wait()
            camera.close()
        frame, info = spy[0]
        self.assertEqual(frame.shape, (480, 640))
        self.assertEqual(info.index, 0)

    def test_the_tree_builds_from_the_proxy(self):
        camera = QRemoteCamera('noise')
        tree = QCameraTree(camera)
        try:
            self.assertIn('blacklevel', tree._parameters)
            tree._parameters['blacklevel'].setValue(60)
            self.assertTrue(wait_for(lambda: camera.blacklevel == 60))
        finally:
            tree.stop()
            camera.close()


@not_on_windows
class TestTheChooser(unittest.TestCase):

    def test_flag_opens_the_camera_in_a_process_of_its_own(self):
        from argparse import ArgumentParser
        from QVideo.cameras.chooser import camera_parser, open_camera
        parser = camera_parser(ArgumentParser())
        with unittest.mock.patch.object(sys, 'argv', ['x', '-r']):
            key, camera = open_camera(parser)
        try:
            self.assertEqual(key, 'noise')
            self.assertIsInstance(camera, QRemoteCamera)
            self.assertTrue(camera.isOpen())
        finally:
            camera.close()

    def test_without_the_flag_the_camera_is_in_this_process(self):
        from argparse import ArgumentParser
        from QVideo.cameras.chooser import camera_parser, open_camera
        parser = camera_parser(ArgumentParser())
        with unittest.mock.patch.object(sys, 'argv', ['x']):
            key, camera = open_camera(parser)
        self.assertNotIsInstance(camera, QRemoteCamera)
        camera.close()


@not_on_windows
class TestStates(unittest.TestCase):

    '''The worker pushes the states of watched nodes between frames.'''

    def setUp(self):
        self.camera = QRemoteCamera(STATES)
        self.addCleanup(self.camera.close)

    def test_nothing_is_cached_until_watched(self):
        time.sleep(0.5)
        self.assertEqual(self.camera.states(['a'], cached=True), {})

    def test_a_watched_node_is_pushed(self):
        self.camera.watch(['a', 'b'])
        self.assertTrue(wait_for(
            lambda: len(self.camera.states(['a', 'b'], cached=True)) == 2))
        state = self.camera.states(['a'], cached=True)['a']
        self.assertNotEqual(state['value'], os.getpid())    # the worker's

    def test_more_nodes_than_a_push_are_all_pushed(self):
        names = [f'n{i}' for i in range(80)]
        self.camera.watch(names)
        self.assertTrue(wait_for(
            lambda: len(self.camera.states(names, cached=True)) == 80))

    def test_cached_states_do_not_ask_the_worker(self):
        with unittest.mock.patch.object(self.camera, '_call') as call:
            self.camera.states(['a'], cached=True)
        call.assert_not_called()

    def test_a_request_reads_and_remembers(self):
        states = self.camera.states(['a'])
        self.assertIn('a', states)
        self.assertEqual(self.camera.states(['a'], cached=True), states)

    def test_a_setting_discards_what_was_pushed(self):
        self.camera.states(['a'])
        self.camera.set('fps', 10)
        self.assertEqual(self.camera.states(['a'], cached=True), {})

    def test_applying_settings_discards_it_too(self):
        self.camera.states(['a'])
        self.camera.settings = {'fps': 10}
        self.assertEqual(self.camera.states(['a'], cached=True), {})


@not_on_windows
class TestTheCameraChangesTheShape(unittest.TestCase):

    '''A shape that the camera changes by itself reaches the proxy.'''

    def test_a_change_that_nobody_asked_for_is_announced(self):
        camera = QRemoteCamera(SHRINKING)
        self.addCleanup(camera.close)
        announced = record(camera.shapeChanged)
        self.assertTrue(wait_for(lambda: announced))
        self.assertEqual((announced[0][0].width(), announced[0][0].height()),
                         (320, 240))

    def test_it_is_announced_once(self):
        camera = QRemoteCamera(SHRINKING)
        self.addCleanup(camera.close)
        announced = record(camera.shapeChanged)
        self.assertTrue(wait_for(lambda: announced))
        time.sleep(0.5)
        app.processEvents()
        self.assertEqual(len(announced), 1)

    def test_a_shape_that_the_proxy_has_is_not_announced_again(self):
        camera = QRemoteCamera('noise')
        self.addCleanup(camera.close)
        announced = record(camera.shapeChanged)
        camera._changed((640, 480))
        self.assertEqual(announced, [])


@not_on_windows
class TestTheWorkerSpeaks(unittest.TestCase):

    def test_the_listener_sorts_answers_from_events(self):
        camera = QRemoteCamera('noise')
        self.addCleanup(camera.close)
        ours, theirs = socket.socketpair()
        replies, handled = queue.Queue(), []
        listener = threading.Thread(
            target=camera._listen,
            args=(Connection(ours.detach()), replies))
        sender = Connection(theirs.detach())
        with unittest.mock.patch.object(
                camera, '_handle', lambda *event: handled.append(event)), \
                unittest.mock.patch.object(camera, '_gone'):
            listener.start()
            sender.send((EVENT, 'a', 1))
            sender.send((REPLY, True, 7))
            sender.send((EVENT, 'b', 2))
            sender.close()
            listener.join(5.)
        camera._ended = False               # it is the listener of a test
        self.assertEqual(handled, [('a', 1), ('b', 2)])
        self.assertEqual(replies.get_nowait(), [True, 7])
        self.assertIsNone(replies.get_nowait())     # the worker has gone

    def test_a_failed_read_reaches_the_log(self):
        camera = QRemoteCamera(FAILING)
        self.addCleanup(camera.close)
        with self.assertLogs(LOGGER, 'ERROR') as logs:
            self.assertTrue(wait_for(lambda: logs.records))
        self.assertIn('no sensor', logs.output[0])

    def test_a_frame_that_cannot_be_published_reaches_the_log(self):
        camera = QRemoteCamera(FLOATING)
        self.addCleanup(camera.close)
        with self.assertLogs(LOGGER, 'ERROR') as logs:
            self.assertTrue(wait_for(lambda: logs.records))
        self.assertIn('float64', logs.output[0])

    def test_a_camera_that_fails_over_and_over_is_reported_once_a_second(
            self):
        camera = QRemoteCamera(FAILING)
        self.addCleanup(camera.close)
        with self.assertLogs(LOGGER, 'ERROR') as logs:
            time.sleep(2.2)
        self.assertGreaterEqual(len(logs.records), 1)
        self.assertLessEqual(len(logs.records), 4)

    def test_answers_arrive_while_events_do(self):
        camera = QRemoteCamera(FAILING)
        self.addCleanup(camera.close)
        end = time.perf_counter() + 1.5
        while time.perf_counter() < end:
            self.assertEqual(camera.get('fps'), 30.)

    def test_a_worker_that_ends_is_noticed_without_a_read(self):
        camera = QRemoteCamera('noise')
        self.addCleanup(camera.close)
        with self.assertLogs(LOGGER, 'ERROR') as logs:
            camera._process.kill()
            self.assertTrue(wait_for(lambda: camera._lost))
        self.assertIn('ended', logs.output[0])

    def test_closing_is_not_a_loss(self):
        camera = QRemoteCamera('noise')
        with self.assertNoLogs(LOGGER, 'ERROR'):
            camera.close()
        self.assertFalse(camera._lost)

    def test_a_camera_that_does_not_open_leaves_nothing_behind(self):
        threads = threading.active_count()
        with self.assertNoLogs(LOGGER, 'ERROR'):
            with self.assertRaises(QCameraError):
                QRemoteCamera('nothing')
        self.assertEqual(threading.active_count(), threads)


@not_on_windows
class TestTheWorkerLeavesWithTheParent(unittest.TestCase):

    def test_worker_exits_when_the_parent_is_killed(self):
        script = ('import time\n'
                  'from QVideo.lib.QRemoteCamera import QRemoteCamera\n'
                  'c = QRemoteCamera("noise")\n'
                  'print(c._process.pid, flush=True)\n'
                  'time.sleep(60)\n')
        parent = subprocess.Popen([sys.executable, '-c', script],
                                  stdout=subprocess.PIPE, text=True)
        pid = int(parent.stdout.readline())
        self.assertTrue(alive(pid))
        parent.send_signal(signal.SIGKILL)
        parent.wait()
        self.assertTrue(wait_for(lambda: not alive(pid)))


if __name__ == '__main__':
    unittest.main()
