'''Show the frames of a source in web browsers.'''
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import socket
import struct
import threading
from typing import Any

import cv2
import numpy as np
from qtpy import QtCore

from QVideo.lib._qapp import stopAtQuit
from QVideo.lib._webpage import PAGE
from QVideo.lib.imageops import AutoLevels, to8bit
from QVideo.lib.videotypes import FrameInfo, Image


logger = logging.getLogger(__name__)

__all__ = ['QWebScreen']

#: Frames between estimates of the levels that ``autoLevels`` follows.
_AUTO_EVERY = 4


def _lanAddress() -> str:
    '''Return the address of this machine on the local network.

    Connecting a UDP socket sends nothing; it only asks the system which
    interface would be used.
    '''
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1', 9))     # a documentation address
            return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'


class _Client:

    '''One browser: the newest message that it has not been sent yet.

    A message that arrives before the previous one is sent replaces it, so a
    slow tablet gets the newest frame and no one waits for it.
    '''

    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.message: bytes | None = None
        self.ready = asyncio.Event()

    def put(self, message: bytes) -> None:
        self.message = message
        self.ready.set()

    async def run(self) -> None:
        '''Send the newest message, as often as there is one, until the
        connection ends.'''
        try:
            while True:
                await self.ready.wait()
                self.ready.clear()
                message, self.message = self.message, None
                if message is not None:
                    await self.ws.send_bytes(message)
        except (ConnectionError, RuntimeError):
            return              # the browser went away


class QWebScreen(QtCore.QObject):

    '''Shows the video of a source in web browsers on the network.

    The counterpart of :class:`~QVideo.lib.QVideoScreen.QVideoScreen` for
    a viewer that is not a Qt window: a tablet, a phone or another computer.
    Open :attr:`url` in a browser.  Several browsers can watch at once.  The
    page has no controls (tap it to hide the frame readout).

    Every frame goes out with its metadata in one message, so whatever is
    drawn with a frame belongs to that frame.  A browser that cannot keep up
    gets the newest frame and skips the rest, and the encoding is done once
    for all browsers, and not at all while there are none.

    There is **no authentication**: anyone who can reach the port sees the
    video.  Use it on a trusted network.

    Parameters
    ----------
    source : QVideoSource, optional
        The source of the frames: a camera's source, or a filter pipeline
        (``web.source = rack.pipeline`` shows what the filters make).
    host : str
        The interface to listen on.  Default ``'0.0.0.0'`` (all of them);
        ``'127.0.0.1'`` serves this machine only.
    port : int
        The port.  Default 8080; ``0`` takes any free one.
    maxWidth : int
        Wider frames are scaled down to this width [pixels].  Default 1024.
    quality : int
        JPEG quality, 1 to 100.  Default 70.
    framerate : float
        The most frames a second that are sent.  Default 30.
    parent : QObject, optional
        Qt parent.

    Notes
    -----
    A frame of more than 8 bits is shown between the levels that it comes
    with, as :class:`~QVideo.lib.QVideoScreen.QVideoScreen` does: the
    explicit :attr:`levels`, then :attr:`autoLevels`, then the levels of the
    frame.  The server needs ``aiohttp``: ``pip install "QVideo[stream]"``.

    Signals
    -------
    clientsChanged(int)
        The number of browsers that are watching.
    '''

    #: Emitted with the number of browsers that watch, when it changes.
    clientsChanged = QtCore.Signal(int)

    def __init__(self,
                 source=None,
                 host: str = '0.0.0.0',
                 port: int = 8080,
                 maxWidth: int = 1024,
                 quality: int = 70,
                 framerate: float = 30.,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.host = host
        self.port = port
        self.maxWidth = maxWidth
        self.quality = quality
        self.framerate = framerate
        self._levels: tuple[float, float] | None = None
        self._auto: AutoLevels | None = None
        self._source = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[_Client] = set()
        self._lock = threading.Lock()
        self._latest: tuple[Image, FrameInfo | None] | None = None
        self._scheduled = False
        self._last: bytes | None = None
        self._count = 0
        self._error: BaseException | None = None
        self.source = source
        stopAtQuit(self.stop)

    # ------------------------------------------------------------------
    # What to show
    # ------------------------------------------------------------------

    @property
    def source(self):
        '''The source whose frames are shown.'''
        return self._source

    @source.setter
    def source(self, source) -> None:
        if self._source is not None:
            self._source.newFrame.disconnect(self._offer)
        self._source = source
        if source is not None:
            # Direct: the frame is stored in the capture thread, and
            # encoded in the thread of the server.
            source.newFrame.connect(
                self._offer, QtCore.Qt.ConnectionType.DirectConnection)

    @property
    def levels(self) -> tuple[float, float] | None:
        '''The pixel values that are shown as black and white, or ``None``.

        With ``None`` (the default) each frame brings its own levels, and a
        frame that has none fills the range of its type.
        '''
        return self._levels

    @levels.setter
    def levels(self, levels: tuple[float, float] | None) -> None:
        if levels is not None and not levels[1] > levels[0]:
            raise ValueError(
                f'the white level must be above the black level: {levels}')
        self._levels = levels

    @property
    def autoLevels(self) -> tuple[float, float] | None:
        '''The percentiles that are shown as black and white, or ``None``.

        The same rule as ``QVideoScreen.autoLevels``: the levels are
        estimated from the frames and smoothed.  Explicit :attr:`levels`
        win.
        '''
        return self._auto.percentiles if self._auto else None

    @autoLevels.setter
    def autoLevels(self, percentiles: tuple[float, float] | None) -> None:
        self._auto = (None if percentiles is None
                      else AutoLevels(percentiles, every=_AUTO_EVERY))

    # ------------------------------------------------------------------
    # The server
    # ------------------------------------------------------------------

    @property
    def url(self) -> str:
        '''The address to open in a browser (valid once started).'''
        host = _lanAddress() if self.host in ('', '0.0.0.0') else self.host
        return f'http://{host}:{self.port}/'

    @property
    def clients(self) -> int:
        '''The number of browsers that are watching.'''
        return len(self._clients)

    def isRunning(self) -> bool:
        '''Return whether the server is up.'''
        return self._thread is not None

    def start(self) -> QWebScreen:
        '''Start the server, in a thread of its own.

        Returns
        -------
        QWebScreen
            ``self``, to allow chaining.

        Raises
        ------
        ImportError
            If ``aiohttp`` is not installed.
        OSError
            If the port cannot be used.
        '''
        if self._thread is not None:
            return self
        try:
            from aiohttp import web
        except ImportError as error:
            raise ImportError('QWebScreen needs aiohttp: '
                              'pip install "QVideo[stream]"') from error
        ready = threading.Event()
        self._error = None
        self._thread = threading.Thread(
            target=self._serve, args=(web, ready), name='QWebScreen',
            daemon=True)
        self._thread.start()
        ready.wait(10.)
        if self._error is not None:
            error, self._error = self._error, None
            self._thread.join()
            self._thread = None
            raise error
        logger.info(f'QWebScreen: open {self.url} in a browser')
        return self

    def stop(self) -> None:
        '''Stop the server and disconnect the browsers.  Safe to repeat.'''
        thread, loop = self._thread, self._loop
        if thread is None:
            return
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._halt.set)
        thread.join(10.)
        self._thread = self._loop = None

    def _serve(self, web, ready: threading.Event) -> None:
        '''The thread of the server: run the event loop until stopped.'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._run(web, ready))
        except BaseException as error:      # reported by start()
            self._error = error
            ready.set()
        finally:
            loop.close()

    async def _run(self, web, ready: threading.Event) -> None:
        self._wake = asyncio.Event()
        self._halt = asyncio.Event()
        app = web.Application()
        app.router.add_get('/', self._index)
        app.router.add_get('/ws', self._socket)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, self.host, self.port).start()
            self.port = runner.addresses[0][1]
            self._web = web
            encoder = asyncio.create_task(self._encode())
            ready.set()
            await self._halt.wait()
            encoder.cancel()
            for client in list(self._clients):
                await client.ws.close(code=1001)    # going away
        finally:
            await runner.cleanup()

    async def _index(self, request):
        return self._web.Response(text=PAGE, content_type='text/html')

    async def _socket(self, request):
        ws = self._web.WebSocketResponse(heartbeat=20.)
        await ws.prepare(request)
        client = _Client(ws)
        self._clients.add(client)
        self.clientsChanged.emit(len(self._clients))
        if self._last is not None:      # a new browser sees the last frame
            client.put(self._last)
        sender = asyncio.create_task(client.run())
        try:
            async for _ in ws:
                pass                    # the page sends nothing, yet
        finally:
            sender.cancel()
            self._clients.discard(client)
            self.clientsChanged.emit(len(self._clients))
        return ws

    # ------------------------------------------------------------------
    # Frames
    # ------------------------------------------------------------------

    @QtCore.Slot(np.ndarray, object)
    def _offer(self, frame: Image, info: FrameInfo | None = None) -> None:
        '''Keep the newest frame; runs in the thread that emitted it.'''
        loop = self._loop
        if loop is None or not self._clients:
            return
        with self._lock:
            self._latest = (frame, info)
            scheduled, self._scheduled = self._scheduled, True
        if not scheduled:
            with contextlib.suppress(RuntimeError):     # the loop has closed
                loop.call_soon_threadsafe(self._wake.set)

    def _take(self) -> tuple[Image, FrameInfo | None] | None:
        with self._lock:
            item, self._latest, self._scheduled = self._latest, None, False
        return item

    async def _encode(self) -> None:
        '''Encode the newest frame, at most :attr:`framerate` times a
        second, for all browsers at once.'''
        loop = asyncio.get_running_loop()
        last = 0.
        while True:
            await self._wake.wait()
            self._wake.clear()
            if not self._clients:
                self._take()            # nobody to show it to
                continue
            wait = last + 1. / self.framerate - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            item = self._take()
            if item is None:
                continue
            try:
                message = await loop.run_in_executor(None, self._pack, *item)
            except Exception:
                logger.exception('QWebScreen: a frame could not be encoded')
                continue
            last = loop.time()
            self._last = message
            for client in list(self._clients):
                client.put(message)

    def _eightBits(self, frame: Image, info: FrameInfo | None) -> Image:
        '''Return the frame as 8 bits, between the levels that apply.'''
        levels = self._levels
        if levels is None and self._auto is not None:
            levels = self._auto(frame)
        if levels is None and info is not None:
            levels = info.levels
        if frame.dtype == np.uint8:
            if levels is None or tuple(levels) == (0, 255):
                return frame
        elif frame.dtype != np.uint16:
            raise TypeError(f'frames of {frame.dtype} cannot be shown')
        return to8bit(frame, levels)

    def _pack(self, frame: Image, info: FrameInfo | None) -> bytes:
        '''Return the message for a frame: the length of the header (4
        bytes, big endian), the header (JSON) and the picture (JPEG).'''
        height, width = frame.shape[:2]
        image = self._eightBits(frame, info)
        if width > self.maxWidth:
            size = (self.maxWidth, round(height * self.maxWidth / width))
            image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
        if image.ndim == 3:
            image = cv2.cvtColor(image[..., :3], cv2.COLOR_RGB2BGR)
        ok, jpeg = cv2.imencode(
            '.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, int(self.quality)])
        if not ok:
            raise ValueError('the frame could not be encoded')
        self._count += 1
        header = dict(
            version=1,
            index=info.index if info else self._count,
            time=info.timestamp if info else None,
            width=width,
            height=height,
            levels=(list(info.levels) if info and info.levels else None),
            overlays=[])
        text = json.dumps(header).encode()
        return struct.pack('>I', len(text)) + text + jpeg.tobytes()

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Serve the video of the camera that the command line chooses.'''
        import sys
        from qtpy import QtWidgets
        from QVideo.cameras import chooser
        from QVideo.lib import QVideoSource
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
            sys.argv)
        key, camera = chooser.open_camera()
        source = QVideoSource(camera).start()
        web = cls(source)
        try:
            web.start()
        except OSError:
            web.port = 0                # 8080 is taken: any free port
            web.start()
        print(f'Open {web.url} in a browser.  Ctrl-C stops.')
        app.exec()
        source.stop()
        web.stop()
        camera.close()


if __name__ == '__main__':  # pragma: no cover
    QWebScreen.example()
