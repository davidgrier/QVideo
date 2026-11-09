'''The web demo shows the video in the window and in a browser at once.'''
import asyncio
import time
import unittest

from qtpy import QtWidgets

from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.webdemo import WebDemo
from QVideo.lib import QVideoScreen
from QVideo.lib.QWebScreen import QWebScreen

try:
    import aiohttp
except ImportError:                     # pragma: no cover
    aiohttp = None


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@unittest.skipIf(aiohttp is None, 'aiohttp not installed')
class TestWebDemo(unittest.TestCase):

    def setUp(self):
        self.tree = QNoiseTree()
        self.demo = WebDemo(self.tree)
        self.demo.web.stop()
        self.demo.web.host = '127.0.0.1'
        self.demo.web.access = False
        self.demo.web.port = 0
        self.demo.web.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.demo.web.stop()
        self.tree.stop()
        app.aboutToQuit.emit()

    def test_both_screens_watch_the_same_source(self):
        self.assertIsInstance(self.demo.screen, QVideoScreen)
        self.assertIsInstance(self.demo.web, QWebScreen)
        self.assertIs(self.demo.web.source, self.demo.screen.source)
        self.assertIs(self.demo.web.source, self.tree.source)

    def test_the_panel_counts_the_viewers(self):
        self.assertEqual(self.demo.viewers.text(), '0 watching')

    def test_the_share_button_shows_and_closes_the_pairing_window(self):
        self.demo.share.close()
        self.assertFalse(self.demo.web.pairing)
        self.demo.shareButton.click()
        self.assertTrue(self.demo.share.isVisible())
        self.assertTrue(self.demo.web.pairing)
        self.demo.shareButton.click()
        self.assertFalse(self.demo.share.isVisible())
        self.assertFalse(self.demo.web.pairing)

    def test_the_window_and_a_browser_both_get_frames(self):
        shown = []
        self.demo.screen.newFrame.connect(
            lambda frame, info=None: shown.append(frame.shape))
        self.tree.start()

        async def watch(port):
            async with aiohttp.ClientSession() as session:
                url = f'http://127.0.0.1:{port}/ws'
                async with session.ws_connect(url) as ws:
                    count = 0
                    deadline = time.monotonic() + 5.
                    while count < 5 and time.monotonic() < deadline:
                        message = await ws.receive(timeout=2.)
                        if message.type == aiohttp.WSMsgType.BINARY:
                            count += 1
                    return count, self.demo.web.clients
        count, watching = asyncio.run(watch(self.demo.web.port))
        deadline = time.monotonic() + 3.
        while not shown and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        self.assertEqual(count, 5)
        self.assertEqual(watching, 1)
        self.assertTrue(shown)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
