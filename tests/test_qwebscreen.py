'''Unit tests for QWebScreen.'''
import asyncio
import json
import struct
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from qtpy import QtCore, QtWidgets

from QVideo.lib.QWebScreen import QWebScreen
from QVideo.lib.videotypes import FrameInfo
from QVideo.tests.signals import record

try:
    import aiohttp
except ImportError:                     # pragma: no cover
    aiohttp = None


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Source(QtCore.QObject):
    '''Stands in for a QVideoSource.'''
    newFrame = QtCore.Signal(np.ndarray, object)
    shapeChanged = QtCore.Signal(QtCore.QSize)

    def send(self, frame, index=0, levels=None):
        info = FrameInfo(index, float(index), levels=levels)
        self.newFrame.emit(frame, info)
        return info


def gradient(height=48, width=64, dtype=np.uint8, top=255):
    row = np.linspace(0, top, width).astype(dtype)
    return np.tile(row, (height, 1))


def unpack(message: bytes):
    '''Return the header and the picture of a message.'''
    (size,) = struct.unpack('>I', message[:4])
    header = json.loads(message[4:4 + size])
    picture = cv2.imdecode(np.frombuffer(message[4 + size:], np.uint8),
                           cv2.IMREAD_UNCHANGED)
    return header, picture


@unittest.skipIf(aiohttp is None, 'aiohttp not installed')
class ServerCase(unittest.TestCase):

    def setUp(self):
        self.source = _Source()
        self.web = QWebScreen(self.source, host='127.0.0.1', port=0,
                              framerate=1000.)
        self.web.start()
        self.addCleanup(self.web.stop)

    def run_client(self, coroutine, *args):
        '''Run a coroutine that talks to the server, in a loop of its own.'''
        return asyncio.run(coroutine(f'http://127.0.0.1:{self.web.port}',
                                     *args))

    async def frames(self, base, send, count=1, timeout=5.):
        '''Connect, call *send* until *count* messages came; return them.'''
        out = []
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(base + '/ws') as ws:
                deadline = time.monotonic() + timeout
                while len(out) < count and time.monotonic() < deadline:
                    send()
                    try:
                        message = await ws.receive(timeout=0.05)
                    except asyncio.TimeoutError:
                        continue
                    if message.type == aiohttp.WSMsgType.BINARY:
                        out.append(message.data)
        return out


@unittest.skipIf(aiohttp is None, 'aiohttp not installed')
class TestServing(ServerCase):

    def test_the_page_is_served(self):
        async def get(base):
            async with aiohttp.ClientSession() as session:
                async with session.get(base + '/') as response:
                    return response.status, await response.text()
        status, text = self.run_client(get)
        self.assertEqual(status, 200)
        self.assertIn('<canvas', text)
        self.assertIn('/ws', text)

    def test_the_port_is_known_once_started(self):
        self.assertGreater(self.web.port, 0)
        self.assertTrue(self.web.url.endswith(f':{self.web.port}/'))
        self.assertTrue(self.web.isRunning())

    def test_stopping_stops_it_and_is_safe_to_repeat(self):
        self.web.stop()
        self.web.stop()
        self.assertFalse(self.web.isRunning())

    def test_it_can_start_again(self):
        self.web.stop()
        self.web.port = 0
        self.web.start()
        self.assertTrue(self.web.isRunning())

    def test_a_port_in_use_is_an_error(self):
        other = QWebScreen(host='127.0.0.1', port=self.web.port)
        with self.assertRaises(OSError):
            other.start()
        self.assertFalse(other.isRunning())

    def test_without_aiohttp_it_says_what_to_install(self):
        other = QWebScreen(host='127.0.0.1', port=0)
        with patch.dict('sys.modules', {'aiohttp': None}):
            with self.assertRaisesRegex(ImportError, r'QVideo\[stream\]'):
                other.start()


@unittest.skipIf(aiohttp is None, 'aiohttp not installed')
class TestFrames(ServerCase):

    def one(self, frame, **kwargs):
        def send():
            self.source.send(frame, **kwargs)
        (message,) = self.run_client(self.frames, send)
        return unpack(message)

    def test_a_frame_arrives_with_its_header(self):
        header, picture = self.one(gradient(48, 64), index=7)
        self.assertEqual(header['version'], 1)
        self.assertGreaterEqual(header['index'], 7)
        self.assertEqual((header['width'], header['height']), (64, 48))
        self.assertEqual(header['overlays'], [])
        self.assertEqual(picture.shape, (48, 64))

    def test_the_picture_is_the_frame(self):
        frame = gradient(48, 64)
        _, picture = self.one(frame)
        self.assertLess(np.abs(picture.astype(int) - frame).mean(), 4)

    def test_a_color_frame_keeps_its_colors(self):
        frame = np.zeros((48, 64, 3), np.uint8)
        frame[..., 0] = 200                     # red, in RGB order
        _, picture = self.one(frame)
        self.assertEqual(picture.shape, (48, 64, 3))
        b, g, r = (float(picture[..., i].mean()) for i in range(3))
        self.assertGreater(r, 150)
        self.assertLess(b, 50)

    def test_a_wide_frame_is_scaled_to_the_maximum_width(self):
        self.web.maxWidth = 32
        header, picture = self.one(gradient(48, 64))
        self.assertEqual(picture.shape, (24, 32))
        self.assertEqual((header['width'], header['height']), (64, 48))

    def test_a_deep_frame_is_shown_between_its_levels(self):
        frame = gradient(48, 64, np.uint16, top=4095)
        header, picture = self.one(frame, levels=(0., 4095.))
        self.assertEqual(header['levels'], [0., 4095.])
        self.assertEqual(picture.dtype, np.uint8)
        self.assertGreater(int(picture.max()), 240)

    def test_explicit_levels_win(self):
        self.web.levels = (0., 2047.)
        frame = gradient(48, 64, np.uint16, top=4095)
        _, picture = self.one(frame, levels=(0., 4095.))
        self.assertEqual(int(picture[:, -1].min()), 255)     # saturated

    def test_auto_levels_stretch_a_dim_frame(self):
        self.web.autoLevels = (1, 99)
        frame = gradient(48, 64, np.uint16, top=400)
        _, picture = self.one(frame)
        self.assertGreater(int(picture.max()), 200)

    def test_levels_must_have_the_white_above_the_black(self):
        with self.assertRaises(ValueError):
            self.web.levels = (5., 5.)

    def test_a_new_browser_sees_the_last_frame(self):
        self.run_client(self.frames, lambda: self.source.send(gradient()))

        async def late(base):
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(base + '/ws') as ws:
                    return await ws.receive(timeout=2.)
        message = self.run_client(late)
        self.assertEqual(message.type, aiohttp.WSMsgType.BINARY)

    def test_the_newest_frame_wins_for_a_browser_that_is_slow(self):
        async def slow(base):
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(base + '/ws') as ws:
                    await asyncio.sleep(0.2)            # connected, idle
                    for index in range(1, 41):
                        self.source.send(gradient(), index=index)
                        await asyncio.sleep(0.002)
                    await asyncio.sleep(0.5)
                    seen = []
                    while True:
                        try:
                            message = await ws.receive(timeout=0.3)
                        except asyncio.TimeoutError:
                            break
                        seen.append(unpack(message.data)[0]['index'])
                    return seen
        seen = self.run_client(slow)
        self.assertTrue(seen)
        self.assertEqual(seen[-1], 40)
        self.assertEqual(seen, sorted(seen))

    def test_an_unsupported_frame_is_logged_and_skipped(self):
        def bad():
            self.source.send(np.zeros((8, 8), np.float32))
        with self.assertLogs('QVideo.lib.QWebScreen', 'ERROR'):
            self.assertEqual(self.run_client(self.frames, bad, 1, 0.5), [])
        header, picture = self.one(gradient())      # the server goes on
        self.assertEqual(picture.shape, (48, 64))

    def test_nothing_is_encoded_while_nobody_watches(self):
        with patch.object(QWebScreen, '_pack') as pack:
            for index in range(10):
                self.source.send(gradient(), index=index)
            time.sleep(0.1)
        pack.assert_not_called()

    def test_the_browsers_are_counted(self):
        changes = record(self.web.clientsChanged)

        async def watch(base):
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(base + '/ws'):
                    await asyncio.sleep(0.2)
                    return self.web.clients
        self.assertEqual(self.run_client(watch), 1)
        time.sleep(0.2)
        self.assertEqual(self.web.clients, 0)
        app.processEvents()
        self.assertEqual([n for (n,) in changes][:2], [1, 0])

    def test_changing_the_source_disconnects_the_old_one(self):
        other = _Source()
        self.web.source = other
        with patch.object(QWebScreen, '_pack') as pack:
            def send():
                self.source.send(gradient())
            self.run_client(self.frames, send, 1, 0.3)
        pack.assert_not_called()


class TestWithoutAServer(unittest.TestCase):

    def test_it_is_not_running_until_started(self):
        web = QWebScreen(host='127.0.0.1', port=0)
        self.assertFalse(web.isRunning())
        self.assertEqual(web.clients, 0)
        web.stop()

    def test_a_frame_before_the_start_is_ignored(self):
        source = _Source()
        QWebScreen(source, host='127.0.0.1', port=0)
        source.send(gradient())

    def test_the_url_of_all_interfaces_is_an_address_of_this_machine(self):
        web = QWebScreen(port=8123)
        self.assertRegex(web.url, r'^http://[\d.]+:8123/$')
        self.assertNotIn('0.0.0.0', web.url)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
