'''Unit tests for QWebScreen.'''
import asyncio
import json
import os
import shutil
import ssl
import struct
import subprocess
import tempfile
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
                              framerate=1000., access=False)
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

    def test_a_port_in_use_can_fall_back_to_a_free_one(self):
        taken = self.web.port
        other = QWebScreen(host='127.0.0.1', port=taken)
        self.addCleanup(other.stop)
        other.start(fallback=True)
        self.assertTrue(other.isRunning())
        self.assertNotEqual(other.port, taken)

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

    def test_a_hostname_is_the_name_in_the_url_and_the_code(self):
        web = QWebScreen(port=8123, hostname='scope1.example.edu')
        self.assertEqual(web.url, 'http://scope1.example.edu:8123/')
        self.assertTrue(
            web.pairingUrl.startswith('http://scope1.example.edu:8123/join/'))

    def test_the_port_of_the_scheme_is_left_out_of_the_url(self):
        self.assertEqual(
            QWebScreen(port=80, hostname='a.example').url,
            'http://a.example/')
        web = QWebScreen(port=443, hostname='a.example')
        web.certfile = 'cert.pem'               # secure: no server needed
        self.assertEqual(web.url, 'https://a.example/')
        self.assertEqual(
            QWebScreen(port=443, hostname='a.example').url,
            'http://a.example:443/')


@unittest.skipIf(aiohttp is None, 'aiohttp not installed')
class TestAccess(unittest.TestCase):

    '''A browser sees nothing until the instrument pairs it.'''

    def setUp(self):
        self.source = _Source()
        self.web = QWebScreen(self.source, host='127.0.0.1', port=0,
                              framerate=1000.)
        self.web.start()
        self.addCleanup(self.web.stop)
        self.base = f'http://127.0.0.1:{self.web.port}'

    @staticmethod
    def client():
        '''A session that keeps cookies from an IP address, as a browser
        does.'''
        return aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True))

    def code(self):
        return self.web.pairingUrl.rsplit('/', 1)[1]

    def run_client(self, coroutine, *args):
        return asyncio.run(coroutine(*args))

    def pair(self, session, code=None):
        return session.get(f'{self.base}/join/{code or self.code()}',
                           allow_redirects=False)

    def test_nothing_is_served_before_pairing(self):
        async def look():
            async with self.client() as session:
                async with session.get(self.base + '/') as page:
                    status = page.status
                async with session.get(self.base + '/session') as check:
                    checked = check.status
                async with session.get(self.base + '/ws') as ws:
                    socket = ws.status
                return status, checked, socket
        self.assertEqual(self.run_client(look), (401, 401, 401))

    def test_the_code_does_not_work_until_pairing_opens(self):
        async def look():
            async with self.client() as session:
                async with self.pair(session) as reply:
                    return reply.status
        self.assertEqual(self.run_client(look), 403)
        self.assertEqual(self.web.viewers, [])

    def test_pairing_gives_a_cookie_that_opens_the_page_and_the_video(self):
        self.web.openPairing()
        changes = record(self.web.viewersChanged)

        async def look():
            async with self.client() as session:
                async with self.pair(session) as reply:
                    joined = reply.status, reply.headers['Location']
                    cookie = reply.cookies['qvideo']
                async with session.get(self.base + '/') as page:
                    status = page.status
                async with session.get(self.base + '/session') as check:
                    checked = check.status
                async with session.ws_connect(self.base + '/ws') as ws:
                    for _ in range(100):
                        self.source.send(gradient())
                        try:
                            message = await ws.receive(timeout=0.05)
                        except asyncio.TimeoutError:
                            continue
                        if message.type == aiohttp.WSMsgType.BINARY:
                            return joined, status, checked, True, cookie
                return joined, status, checked, False, cookie
        joined, status, checked, got, cookie = self.run_client(look)
        # A scan comes from another app: Strict would lose the cookie in
        # the redirect (found on an iPad, 2026-11-09).
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(joined, (302, '/'))
        self.assertEqual((status, checked), (200, 200))
        self.assertTrue(got)
        (viewer,) = self.web.viewers
        self.assertTrue(viewer['id'])
        app.processEvents()             # the signal crosses threads
        self.assertTrue(changes)

    def test_a_code_pairs_one_browser(self):
        self.web.openPairing()
        code = self.code()
        codes = record(self.web.codeChanged)

        async def look():
            statuses = []
            for _ in range(2):
                async with self.client() as session:
                    async with self.pair(session, code) as reply:
                        statuses.append(reply.status)
            return statuses
        self.assertEqual(self.run_client(look), [302, 403])
        app.processEvents()
        self.assertTrue(codes)
        self.assertNotEqual(self.code(), code)
        self.assertTrue(self.web.pairing)       # the window stays open
        self.assertEqual(len(self.web.viewers), 1)

    def test_a_wrong_code_is_refused(self):
        self.web.openPairing()

        async def look():
            async with self.client() as session:
                async with self.pair(session, 'wrong') as reply:
                    return reply.status
        self.assertEqual(self.run_client(look), 403)
        self.assertEqual(self.web.viewers, [])

    def test_too_many_wrong_codes_block_the_address(self):
        self.web.openPairing()

        async def look():
            statuses = []
            async with self.client() as session:
                for _ in range(7):
                    async with self.pair(session, 'wrong') as reply:
                        statuses.append(reply.status)
                async with self.pair(session) as reply:    # the right one
                    statuses.append(reply.status)
            return statuses
        statuses = self.run_client(look)
        self.assertEqual(statuses[:5], [403] * 5)
        self.assertEqual(statuses[5:], [429] * 3)
        self.assertEqual(self.web.viewers, [])

    def test_closing_the_window_changes_the_secret_but_keeps_viewers(self):
        self.web.openPairing()
        old = self.web.pairingUrl
        codes = record(self.web.codeChanged)
        states = record(self.web.pairingChanged)

        async def look():
            async with self.client() as session:
                async with self.pair(session) as reply:
                    assert reply.status == 302
                self.web.closePairing()
                async with session.get(self.base + '/session') as check:
                    return check.status
        self.assertEqual(self.run_client(look), 200)
        self.assertNotEqual(self.web.pairingUrl, old)
        self.assertEqual(codes, [()])
        self.assertEqual(states, [(False,)])
        self.assertFalse(self.web.pairing)
        self.assertEqual(len(self.web.viewers), 1)

    def test_the_old_code_fails_after_a_new_one(self):
        self.web.openPairing()
        old = self.code()
        self.web.rotate()

        async def look():
            async with self.client() as session:
                async with self.pair(session, old) as reply:
                    return reply.status
        self.assertEqual(self.run_client(look), 403)

    def test_revoking_disconnects_and_unpairs(self):
        self.web.openPairing()

        async def look():
            async with self.client() as session:
                async with self.pair(session):
                    pass
                async with session.ws_connect(self.base + '/ws') as ws:
                    (viewer,) = self.web.viewers
                    self.web.revoke(viewer['id'])
                    while True:
                        message = await ws.receive(timeout=3.)
                        if message.type != aiohttp.WSMsgType.BINARY:
                            break
                    closed = ws.close_code
                async with session.get(self.base + '/session') as check:
                    return closed, check.status
        closed, status = self.run_client(look)
        self.assertEqual(closed, 4401)
        self.assertEqual(status, 401)
        self.assertEqual(self.web.viewers, [])

    def test_revoking_all(self):
        self.web.openPairing()

        async def look():
            for _ in range(2):
                async with self.client() as session:
                    async with self.pair(session):
                        pass
        self.run_client(look)
        self.assertEqual(len(self.web.viewers), 2)
        self.web.revoke()
        self.assertEqual(self.web.viewers, [])

    def test_a_page_from_another_site_cannot_open_the_video(self):
        self.web.openPairing()

        async def look():
            async with self.client() as session:
                async with self.pair(session):
                    pass
                try:
                    await session.ws_connect(
                        self.base + '/ws',
                        headers={'Origin': 'http://evil.example'})
                except aiohttp.WSServerHandshakeError as error:
                    return error.status
        self.assertEqual(self.run_client(look), 403)

    def test_without_access_the_pairing_address_is_the_page(self):
        other = QWebScreen(host='127.0.0.1', port=0, access=False)
        self.assertEqual(other.pairingUrl, other.url)

    def test_the_device_is_named(self):
        from QVideo.lib.QWebScreen import _deviceName
        self.assertEqual(_deviceName('Mozilla/5.0 (iPad; CPU OS 17)'), 'iPad')
        self.assertEqual(_deviceName('curl/8'), 'browser')


def makeCertificate(directory):
    '''Write a self-signed certificate for 127.0.0.1; return its paths, or
    ``None`` if openssl is not there.'''
    if shutil.which('openssl') is None:     # pragma: no cover
        return None
    cert = os.path.join(directory, 'cert.pem')
    key = os.path.join(directory, 'key.pem')
    subprocess.run(
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
         '-keyout', key, '-out', cert, '-days', '2', '-subj',
         '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1'],
        check=True, capture_output=True)
    return cert, key


@unittest.skipIf(aiohttp is None, 'aiohttp not installed')
class TestTls(unittest.TestCase):

    '''With a certificate the server speaks https.'''

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        files = makeCertificate(directory.name)
        if files is None:                   # pragma: no cover
            self.skipTest('openssl not installed')
        self.cert, self.key = files
        self.web = QWebScreen(_Source(), host='127.0.0.1', port=0,
                              certfile=self.cert, keyfile=self.key)
        self.web.start()
        self.addCleanup(self.web.stop)
        self.base = f'https://127.0.0.1:{self.web.port}'
        self.context = ssl.create_default_context(cafile=self.cert)

    def client(self):
        return aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True))

    def test_the_address_is_https(self):
        self.assertTrue(self.web.secure)
        self.assertTrue(self.web.url.startswith('https://'))
        self.assertTrue(self.web.pairingUrl.startswith('https://'))

    def test_pairing_and_the_video_work_over_https(self):
        self.web.openPairing()
        code = self.web.pairingUrl.rsplit('/', 1)[1]

        async def look():
            async with self.client() as session:
                async with session.get(
                        f'{self.base}/join/{code}', ssl=self.context,
                        allow_redirects=False) as reply:
                    cookie = reply.cookies['qvideo']
                async with session.get(self.base + '/',
                                       ssl=self.context) as page:
                    status = page.status
                async with session.ws_connect(
                        self.base + '/ws', ssl=self.context) as ws:
                    opened = not ws.closed
                return cookie, status, opened
        cookie, status, opened = asyncio.run(look())
        self.assertTrue(cookie['secure'])
        self.assertEqual(status, 200)
        self.assertTrue(opened)

    def test_a_browser_that_does_not_trust_the_certificate_is_refused(self):
        async def look():
            async with self.client() as session:
                try:
                    await session.get(self.base + '/')
                except aiohttp.ClientConnectorCertificateError:
                    return True
            return False
        self.assertTrue(asyncio.run(look()))

    def test_plain_http_is_not_served_on_the_port(self):
        async def look():
            async with self.client() as session:
                try:
                    await session.get(
                        f'http://127.0.0.1:{self.web.port}/', timeout=
                        aiohttp.ClientTimeout(total=3))
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    return True
            return False
        self.assertTrue(asyncio.run(look()))

    def test_control_is_available_over_https_and_not_over_http(self):
        from QVideo.cameras.Noise import QNoiseCamera
        camera = QNoiseCamera()
        self.addCleanup(camera.close)
        secure = QWebScreen(camera=camera, certfile=self.cert,
                            keyfile=self.key)
        self.assertTrue(secure.controlAvailable)
        plain = QWebScreen(camera=camera)
        self.assertFalse(plain.controlAvailable)
        self.assertIn('https', plain.controlReason)

    def test_without_a_certificate_the_server_is_not_secure(self):
        other = QWebScreen(host='127.0.0.1', port=0)
        self.assertFalse(other.secure)
        self.assertTrue(other.url.startswith('http://'))

    def test_a_missing_certificate_is_an_error_and_not_a_busy_port(self):
        other = QWebScreen(host='127.0.0.1', port=self.web.port,
                           certfile='/nonexistent.pem')
        with self.assertRaises(OSError):
            other.start(fallback=True)
        self.assertFalse(other.isRunning())
        self.assertEqual(other.port, self.web.port)     # no fallback

    def served(self):
        '''The certificate that the server presents, as PEM.'''
        return ssl.get_server_certificate(('127.0.0.1', self.web.port))

    def restart(self, renew=None):
        '''Serve again, and look at the files every 50 ms.'''
        self.web.stop()
        patcher = patch('QVideo.lib.QWebScreen._CERT_EVERY', 0.05)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.web = QWebScreen(_Source(), host='127.0.0.1', port=0,
                              certfile=self.cert, keyfile=self.key)
        self.web._renew = renew
        self.web.start()
        self.addCleanup(self.web.stop)

    def renewed(self):
        '''Replace the files with another certificate; return its PEM.'''
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        cert, key = makeCertificate(directory.name)
        shutil.copyfile(key, self.key)
        shutil.copyfile(cert, self.cert)
        with open(cert) as file:
            return file.read()

    def test_a_renewed_certificate_is_served_after_a_reload(self):
        before = self.served()
        new = self.renewed()
        self.assertEqual(self.served(), before)         # not yet
        self.assertTrue(self.web.reloadCertificate())
        self.assertEqual(self.served().strip(), new.strip())
        self.assertNotEqual(self.served(), before)

    def test_files_that_are_not_a_pair_leave_the_certificate_alone(self):
        before = self.served()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        other, _ = makeCertificate(directory.name)
        shutil.copyfile(other, self.cert)               # the key is not its
        with self.assertLogs('QVideo.lib.QWebScreen', 'ERROR'):
            self.assertFalse(self.web.reloadCertificate())
        self.assertEqual(self.served(), before)

    def test_without_a_certificate_there_is_nothing_to_reload(self):
        self.assertFalse(QWebScreen(port=0).reloadCertificate())

    def test_the_server_notices_a_renewed_certificate_by_itself(self):
        self.restart()
        time.sleep(0.1)
        new = self.renewed()
        os.utime(self.cert, (time.time() + 10, time.time() + 10))
        deadline = time.monotonic() + 5.
        while time.monotonic() < deadline:
            if self.served().strip() == new.strip():
                break
            time.sleep(0.05)
        self.assertEqual(self.served().strip(), new.strip())

    def test_the_server_asks_for_a_renewal_that_the_program_can_make(self):
        calls = []
        self.restart(renew=lambda: calls.append(1))
        deadline = time.monotonic() + 3.
        while not calls and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(calls)

    def test_the_dialog_says_encrypted(self):
        from QVideo.widgets.QWebShareDialog import QWebShareDialog
        dialog = QWebShareDialog(self.web)
        self.addCleanup(dialog.deleteLater)
        labels = [w.text() for w in dialog.findChildren(QtWidgets.QLabel)]
        self.assertIn('Encrypted (https).', labels)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
