'''Show the frames of a source in web browsers.'''
from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
import secrets
import socket
import ssl
import struct
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

import cv2
import numpy as np
from qtpy import QtCore

from QVideo.lib import _webcontrols
from QVideo.lib._qapp import stopAtQuit
from QVideo.lib._webpage import DENIED, EXPIRED, PAGE
from QVideo.lib.imageops import AutoLevels, to8bit
from QVideo.lib.videotypes import FrameInfo, Image


logger = logging.getLogger(__name__)

__all__ = ['QWebScreen']

#: Frames between estimates of the levels that ``autoLevels`` follows.
_AUTO_EVERY = 4

#: The cookie that identifies a paired browser.
_COOKIE = 'qvideo'

#: A paired browser is remembered by the browser for this many seconds.
_COOKIE_AGE = 7 * 24 * 3600

#: This many wrong codes from one address within ``_WINDOW`` seconds block it
#: for the rest of the window.
_ATTEMPTS = 5
_WINDOW = 60.

#: The close code that tells the page that the instrument disconnected it.
_REVOKED = 4401

#: A browser that was refused control waits this long [s] before it can ask
#: again, so that a paired device cannot fill the screen with prompts.
_RETRY = 10.

#: The largest message that a page may send [bytes].
_MAX_MESSAGE = 4096

#: Seconds that changed values wait, so that a camera that reports every
#: frame sends a page one message in a tenth of a second at most.
_VALUES_EVERY = 0.1


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


def _deviceName(agent: str) -> str:
    '''Return a short name for the device that a browser runs on.'''
    for key, name in (('iPad', 'iPad'), ('iPhone', 'iPhone'),
                      ('Android', 'Android'), ('Macintosh', 'Mac'),
                      ('Windows', 'Windows'), ('Linux', 'Linux')):
        if key in agent:
            return name
    return 'browser'


def _plain(value: object) -> object:
    '''Make a NumPy number into a Python one, for JSON.'''
    item = getattr(value, 'item', None)
    if item is None:
        raise TypeError(f'{type(value).__name__} is not JSON')
    return item()


class _Viewer:

    '''A browser that was paired: one device, perhaps with several pages.'''

    def __init__(self, ident: str, address: str, agent: str) -> None:
        self.ident = ident
        self.address = address
        self.name = _deviceName(agent)
        self.since = time.time()
        self.clients: set[_Client] = set()
        self.control = 'none'           # 'none', 'requested' or 'granted'
        self.deniedAt = 0.


class _Client:

    '''One connection: the newest message that it has not been sent yet.

    A message that arrives before the previous one is sent replaces it, so a
    slow tablet gets the newest frame and no one waits for it.  Notes (text
    for the page) are not replaced: each is sent, before the next frame.
    '''

    def __init__(self, ws: Any, viewer: _Viewer | None = None) -> None:
        self.ws = ws
        self.viewer = viewer
        self.message: bytes | None = None
        self.notes: deque[str] = deque()
        self.ready = asyncio.Event()

    def put(self, message: bytes) -> None:
        self.message = message
        self.ready.set()

    def tell(self, note: str) -> None:
        self.notes.append(note)
        self.ready.set()

    async def run(self) -> None:
        '''Send the newest message, as often as there is one, until the
        connection ends.'''
        try:
            while True:
                await self.ready.wait()
                self.ready.clear()
                while self.notes:
                    await self.ws.send_str(self.notes.popleft())
                message, self.message = self.message, None
                if message is not None:
                    await self.ws.send_bytes(message)
        except (ConnectionError, RuntimeError):
            return              # the browser went away


class QWebScreen(QtCore.QObject):

    '''Shows the video of a source in web browsers on the network.

    The counterpart of :class:`~QVideo.lib.QVideoScreen.QVideoScreen` for
    a viewer that is not a Qt window: a tablet, a phone or another computer.
    Several browsers can watch at once.  Tap the page to hide the frame
    readout.  With a ``camera`` the page also offers controls (see below).

    Every frame goes out with its metadata in one message, so whatever is
    drawn with a frame belongs to that frame.  A browser that cannot keep up
    gets the newest frame and skips the rest, and the encoding is done once
    for all browsers, and not at all while there are none.

    **Access.**  A browser must be paired before it sees anything, and it
    pairs by opening :attr:`pairingUrl`, which the instrument shows as a QR
    code (:class:`~QVideo.widgets.QWebShareDialog.QWebShareDialog`).  The
    address works only while the pairing window is open
    (:meth:`openPairing`), and for one browser: the secret changes after
    each pairing, so a link that was read off the network is spent.
    :meth:`closePairing` shuts the window and changes the secret, so a
    photograph of the code is no use afterward.  A paired
    browser keeps a cookie that the server remembers until the program ends
    or :meth:`revoke` removes it.  Wrong codes are limited to a few a minute
    from each address.

    **Encryption** has two tiers (:ref:`streaming-encryption`).  Tier 1, the
    default, is plain http for a network that you trust: anyone who can read
    the network sees the video and the cookie.  Tier 2 is for any other
    network, and for control from a page: give a certificate (``certfile``,
    ``keyfile``) and the name that it covers (``hostname``) and the server
    speaks https, with a ``Secure`` cookie, or run it inside a tunnel (a
    VPN, Tailscale) or behind a proxy.  A certificate that the browsers
    trust is the hard part.

    **Control.**  Pairing lets a browser *look*.  To *change* the camera it
    asks, and the operator answers a prompt on the screen of the instrument
    (:class:`~QVideo.widgets.QWebShareDialog.QWebShareDialog` shows it, or
    a program connects :attr:`controlRequested` to :meth:`grantControl` and
    :meth:`denyControl`).  One browser controls at a time, and control ends
    when its page closes or the operator takes it back
    (:meth:`revokeControl`).  A page can change only the properties named in
    ``properties`` (by default the usual ones: exposure, gain and so on),
    and every value is checked and clipped to the limits of the property.
    Control needs a secure connection (a certificate), because a cookie that
    was read off the network must not move an instrument; a program that
    trusts its network can set ``controlOverHttp``.

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
    certfile, keyfile : str, optional
        The certificate (and its chain) and the private key, in PEM files.
        With them the server speaks https and :attr:`url` begins with
        ``https://``; the certificate must name the host that the browsers
        use.  Without them the connection is not encrypted.
    hostname : str, optional
        The name that browsers use for this machine, such as
        ``'scope1.example.edu'``.  :attr:`url`, and so the QR code, use it
        instead of the address on the local network: a certificate names a
        host, not an address, so a browser accepts it only at that name.
        The name must lead to this machine.  Default ``None``: the address.
    access : bool
        Require pairing.  Default ``True``.  ``False`` serves anyone who
        can reach the port, with no cookie: for a machine that only you
        can reach.  It is view only: with nobody to pair, nobody can ask
        for control.
    camera : QCamera, optional
        The camera whose properties the page may change.  Without one the
        page has no controls.
    properties : sequence of str, optional
        The names of the properties that the page may change.  Default
        ``None``: the usual ones that the camera has and lets us write
        (:data:`~QVideo.lib._webcontrols.COMMON`).  An empty sequence turns
        control off.
    controlOverHttp : bool
        Allow control without a certificate.  Default ``False``.  Anyone
        who can read the network can then take the cookie of the browser
        that controls and set the properties with it: only for a network
        that you trust as you trust the instrument.
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
        The number of connections that are watching.
    viewersChanged()
        A browser paired, connected, disconnected or was removed.
    pairingChanged(bool)
        The pairing window opened or closed.
    codeChanged()
        :attr:`pairingUrl` changed: show the new code.
    controlRequested(str)
        A paired browser asks to control the camera, with the ``id`` of the
        browser (see :attr:`viewers`): answer with :meth:`grantControl` or
        :meth:`denyControl`.
    '''

    #: Emitted with the number of browsers that watch, when it changes.
    clientsChanged = QtCore.Signal(int)

    #: Emitted when a browser pairs, connects, disconnects or is removed.
    viewersChanged = QtCore.Signal()

    #: Emitted with ``True`` when the pairing window opens, ``False`` when
    #: it closes.
    pairingChanged = QtCore.Signal(bool)

    #: Emitted when :attr:`pairingUrl` changes: show the new code.
    codeChanged = QtCore.Signal()

    #: Emitted with the ``id`` of a browser that asks to control the camera.
    controlRequested = QtCore.Signal(str)

    def __init__(self,
                 source=None,
                 host: str = '0.0.0.0',
                 port: int = 8080,
                 maxWidth: int = 1024,
                 quality: int = 70,
                 framerate: float = 30.,
                 access: bool = True,
                 certfile: str | None = None,
                 keyfile: str | None = None,
                 hostname: str | None = None,
                 camera=None,
                 properties: Sequence[str] | None = None,
                 controlOverHttp: bool = False,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.host = host
        self.port = port
        self.maxWidth = maxWidth
        self.quality = quality
        self.framerate = framerate
        self.access = access
        self.certfile = certfile
        self.keyfile = keyfile
        self.hostname = hostname
        self.properties = properties
        self.controlOverHttp = controlOverHttp
        self._camera = None
        self._pool: ThreadPoolExecutor | None = None
        self._tls: ssl.SSLContext | None = None
        self._guard = threading.Lock()      # the secret and the sessions
        self._secret = secrets.token_urlsafe(16)
        self._pairing = False
        self._sessions: dict[str, _Viewer] = {}
        self._failures: dict[str, deque[float]] = {}
        self._levels: tuple[float, float] | None = None
        self._auto: AutoLevels | None = None
        self._source = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[_Client] = set()
        self._heldValues: dict[str, Any] = {}
        self._valuesTimer: asyncio.TimerHandle | None = None
        self._lock = threading.Lock()
        self._latest: tuple[Image, FrameInfo | None] | None = None
        self._scheduled = False
        self._last: bytes | None = None
        self._count = 0
        self._error: BaseException | None = None
        self.source = source
        self.camera = camera
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
    # Access
    # ------------------------------------------------------------------

    @property
    def pairingUrl(self) -> str:
        '''The address that pairs a browser (the one that the QR code
        holds).  It works only while :attr:`pairing` is ``True``.  Without
        :attr:`access` it is :attr:`url`.'''
        if not self.access:
            return self.url
        with self._guard:
            return f'{self.url}join/{self._secret}'

    @property
    def pairing(self) -> bool:
        '''Whether the pairing window is open.'''
        return self._pairing

    def openPairing(self) -> None:
        '''Let browsers pair with :attr:`pairingUrl`.'''
        self._setPairing(True)

    def closePairing(self) -> None:
        '''Stop pairing, and change the secret.  Browsers that are paired
        stay paired.'''
        self._setPairing(False)

    def _setPairing(self, state: bool) -> None:
        with self._guard:
            changed = state != self._pairing
            self._pairing = state
            if not state:
                self._secret = secrets.token_urlsafe(16)
        if changed:
            self.pairingChanged.emit(state)
            if not state:
                self.codeChanged.emit()

    def rotate(self) -> None:
        '''Change the secret: the address and code that were shown no longer
        pair.  Browsers that are paired stay paired.'''
        with self._guard:
            self._secret = secrets.token_urlsafe(16)
        self.codeChanged.emit()

    @property
    def viewers(self) -> list[dict[str, Any]]:
        '''The paired browsers, as dicts with ``id``, ``name`` (the kind of
        device), ``address``, ``since`` (a time), ``watching`` (whether
        a page is open) and ``control`` (``'none'``, ``'requested'`` or
        ``'granted'``).'''
        with self._guard:
            return [dict(id=v.ident, name=v.name, address=v.address,
                         since=v.since, watching=bool(v.clients),
                         control=v.control)
                    for v in self._sessions.values()]

    def revoke(self, ident: str | None = None) -> None:
        '''Unpair a browser, or all of them if *ident* is ``None``.

        The browser is disconnected, and must pair again to see the video.
        '''
        with self._guard:
            if ident is None:
                gone = list(self._sessions.values())
                self._sessions.clear()
            else:
                gone = [v for v in (self._sessions.pop(ident, None),) if v]
        loop = self._loop
        if loop is not None and not loop.is_closed():
            for viewer in gone:
                asyncio.run_coroutine_threadsafe(self._drop(viewer), loop)
        if gone:
            self.viewersChanged.emit()

    @staticmethod
    async def _drop(viewer: _Viewer) -> None:
        for client in list(viewer.clients):
            await client.ws.close(code=_REVOKED)

    def _viewerOf(self, request) -> _Viewer | None:
        token = request.cookies.get(_COOKIE)
        with self._guard:
            return self._sessions.get(token) if token else None

    def _blocked(self, address: str) -> bool:
        '''Return whether *address* has failed too often lately.'''
        failures = self._failures.get(address)
        if failures is None:
            return False
        now = time.monotonic()
        while failures and now - failures[0] > _WINDOW:
            failures.popleft()
        if not failures:
            del self._failures[address]
            return False
        return len(failures) >= _ATTEMPTS

    def _fail(self, address: str) -> None:
        self._failures.setdefault(address, deque()).append(time.monotonic())

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    @property
    def camera(self):
        '''The camera whose properties a page may change, or ``None``.'''
        return self._camera

    @camera.setter
    def camera(self, camera) -> None:
        if self._camera is not None:
            self._camera.propertiesChanged.disconnect(self._changed)
        self._camera = camera
        if camera is not None:
            # Queued: the camera reports from its own threads.
            camera.propertiesChanged.connect(self._changed)

    def _exposed(self) -> list[str]:
        '''Return the names of the properties that a page may change.'''
        if self._camera is None:
            return []
        return _webcontrols.choose(self._camera.properties, self.properties)

    @property
    def controlNames(self) -> list[str]:
        '''The names of the properties that a page may change.'''
        return self._exposed()

    def _controlState(self) -> tuple[bool, str]:
        '''Return whether a page can control the camera, and if not, why.'''
        if self._camera is None or not self._exposed():
            return False, 'there is nothing to control'
        if not self.access:
            return False, 'pairing is off'
        if not (self.secure or self.controlOverHttp):
            return False, 'control needs a secure connection (https)'
        return True, ''

    @property
    def controlAvailable(self) -> bool:
        '''Whether a paired browser can ask to control the camera.'''
        return self._controlState()[0]

    @property
    def controlReason(self) -> str:
        '''Why :attr:`controlAvailable` is ``False`` (empty if it is not).'''
        return self._controlState()[1]

    @property
    def controller(self) -> str | None:
        '''The ``id`` of the browser that controls the camera, or ``None``.'''
        with self._guard:
            for viewer in self._sessions.values():
                if viewer.control == 'granted':
                    return viewer.ident
        return None

    def grantControl(self, ident: str) -> bool:
        '''Let the browser *ident* control the camera, and nobody else.

        A browser that controlled it before is told that it does not.

        Returns
        -------
        bool
            ``False`` if there is no such browser or control is not
            available.
        '''
        if not self.controlAvailable:
            return False
        with self._guard:
            viewer = self._sessions.get(ident)
            if viewer is None:
                return False
            changed = [v for v in self._sessions.values()
                       if v.control == 'granted' and v is not viewer]
            for other in changed:
                other.control = 'none'
            viewer.control = 'granted'
        for other in changed:
            self._notify(other, 'revoked')
        self._notify(viewer, 'granted')
        self.viewersChanged.emit()
        return True

    def denyControl(self, ident: str) -> None:
        '''Refuse the request of the browser *ident* to control the camera.

        The browser can ask again after a few seconds.
        '''
        with self._guard:
            viewer = self._sessions.get(ident)
            if viewer is None or viewer.control != 'requested':
                return
            viewer.control = 'none'
            viewer.deniedAt = time.monotonic()
        self._notify(viewer, 'denied')
        self.viewersChanged.emit()

    def revokeControl(self, ident: str | None = None) -> None:
        '''Take control back from the browser *ident*, or from whichever
        browser has it if *ident* is ``None``.'''
        with self._guard:
            gone = [v for v in self._sessions.values()
                    if v.control == 'granted'
                    and ident in (None, v.ident)]
            for viewer in gone:
                viewer.control = 'none'
        for viewer in gone:
            self._notify(viewer, 'revoked')
        if gone:
            self.viewersChanged.emit()

    def _notify(self, viewer: _Viewer, state: str) -> None:
        '''Tell the pages of *viewer* what became of their control.'''
        available, reason = self._controlState()
        self._tellViewer(viewer, dict(type='control', state=state,
                                      available=available, reason=reason))

    def _tellViewer(self, viewer: _Viewer, note: dict) -> None:
        text = json.dumps(note)
        self._inLoop(lambda: [c.tell(text) for c in list(viewer.clients)])

    def _tellAll(self, note: dict) -> None:
        text = json.dumps(note, default=_plain)
        self._inLoop(lambda: [c.tell(text) for c in list(self._clients)])

    def _inLoop(self, call) -> None:
        '''Run *call* in the thread of the server, from any thread.'''
        loop = self._loop
        if loop is not None and not loop.is_closed():
            with contextlib.suppress(RuntimeError):     # the loop has closed
                loop.call_soon_threadsafe(call)

    @QtCore.Slot(object)
    def _changed(self, values: dict) -> None:
        '''Tell the pages that properties changed (a page set one, or the
        camera did by itself).'''
        names = set(self._exposed())
        shown = {key: value for key, value in values.items() if key in names}
        if shown:
            self._inLoop(lambda: self._queueValues(shown))

    def _queueValues(self, shown: dict) -> None:
        '''Hold changed values for a moment and send each page the newest
        of each in one message.  Every value is sent, even one that did not
        change: a page that asked for a value the camera did not accept
        needs to hear what the camera has.  Runs in the thread of the
        server.'''
        loop = self._loop
        if loop is None:
            return
        self._heldValues.update(shown)
        if self._valuesTimer is None:
            self._valuesTimer = loop.call_later(
                _VALUES_EVERY, self._sendValues)

    def _sendValues(self) -> None:
        self._valuesTimer = None
        held, self._heldValues = self._heldValues, {}
        if held:
            text = json.dumps(dict(type='values', values=held),
                              default=_plain)
            for client in list(self._clients):
                client.tell(text)

    async def _hello(self, client: _Client) -> None:
        '''Send a page what it needs to build its controls.'''
        camera = self._camera
        names = self._exposed()
        available, reason = self._controlState()
        entries: list[dict] = []
        if camera is not None and names and self._pool is not None:
            loop = asyncio.get_running_loop()
            values = await loop.run_in_executor(
                self._pool, camera.snapshot, names)
            entries = _webcontrols.describe(camera.properties, names, values)
        viewer = client.viewer
        client.tell(json.dumps(
            dict(type='hello', secure=self.secure, available=available,
                 reason=reason, controls=entries,
                 state=viewer.control if viewer else 'none'),
            default=_plain))

    async def _handle(self, client: _Client, text: str) -> None:
        '''Act on a message from a page.  A page is not trusted: anything
        that is not understood, or not allowed, is ignored.'''
        viewer = client.viewer
        try:
            message = json.loads(text)
        except ValueError:
            return
        if viewer is None or not isinstance(message, dict):
            return
        kind = message.get('type')
        if kind == 'request':
            self._request(viewer)
        elif kind == 'release':
            self._release(viewer)
        elif kind == 'set':
            await self._set(viewer, message.get('name'),
                            message.get('value'))

    def _request(self, viewer: _Viewer) -> None:
        available, _ = self._controlState()
        with self._guard:
            if not available or viewer.control != 'none':
                state = viewer.control
                ask = False
            elif time.monotonic() - viewer.deniedAt < _RETRY:
                state, ask = 'denied', False
            else:
                viewer.control = state = 'requested'
                ask = True
        self._notify(viewer, state if available else 'none')
        if ask:
            self.viewersChanged.emit()
            self.controlRequested.emit(viewer.ident)

    def _release(self, viewer: _Viewer) -> None:
        with self._guard:
            held, viewer.control = viewer.control, 'none'
        if held != 'none':
            self._notify(viewer, 'none')
            self.viewersChanged.emit()

    async def _set(self, viewer: _Viewer, name: object,
                   value: object) -> None:
        camera = self._camera
        if (camera is None or viewer.control != 'granted'
                or not self._controlState()[0]
                or not isinstance(name, str)
                or name not in self._exposed()):
            return
        try:
            value = _webcontrols.coerce(camera.properties[name], value)
        except ValueError as error:
            logger.debug(f'QWebScreen: {name}: {error}')
            return
        if self._pool is not None:
            await asyncio.get_running_loop().run_in_executor(
                self._pool, self._apply, camera, name, value)

    def _apply(self, camera, name: str, value: object) -> None:
        '''Set a property, in a thread that may wait for the camera, and
        say what the exposed properties are now.'''
        try:
            camera.set(name, value)
            # What the pages show, and what a tree that watches the camera
            # shows (a new resolution changes the width in the tree).
            names = self._exposed()
            names += [key for key in getattr(camera, '_watched', ())
                      if key not in names]
            camera.propertiesChanged.emit(camera.snapshot(names))
        except Exception:
            logger.exception(f'QWebScreen: {name} could not be set')

    # ------------------------------------------------------------------
    # The server
    # ------------------------------------------------------------------

    @property
    def url(self) -> str:
        '''The address to open in a browser (valid once started): the
        ``hostname`` if there is one, otherwise the address of this machine
        on the local network.  The port is left out where it is the
        default of the scheme (443 for https).'''
        host = self.hostname
        if not host:
            host = (_lanAddress() if self.host in ('', '0.0.0.0')
                    else self.host)
        scheme = 'https' if self.secure else 'http'
        default = 443 if self.secure else 80
        port = '' if self.port == default else f':{self.port}'
        return f'{scheme}://{host}{port}/'

    @property
    def secure(self) -> bool:
        '''Whether the connection is encrypted (a certificate was given).'''
        return self.certfile is not None

    @property
    def clients(self) -> int:
        '''The number of browsers that are watching.'''
        return len(self._clients)

    def isRunning(self) -> bool:
        '''Return whether the server is up.'''
        return self._thread is not None

    def start(self, fallback: bool = False) -> QWebScreen:
        '''Start the server, in a thread of its own.

        Parameters
        ----------
        fallback : bool
            If the port is taken, take any free port instead of raising.
            Default ``False``.

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
        ssl.SSLError
            If the certificate and the key cannot be used.
        '''
        if self._thread is not None:
            return self
        # Read the certificate first: a bad file is not a busy port.
        self._tls = self._context()
        try:
            return self._start()
        except OSError:
            if not fallback:
                raise
            logger.info(f'port {self.port} is taken: using another')
            self.port = 0
            return self._start()

    def _context(self) -> ssl.SSLContext | None:
        '''Return the TLS settings, or ``None`` for plain http.'''
        if self.certfile is None:
            return None
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.certfile, self.keyfile)
        return context

    def _start(self) -> QWebScreen:
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
        logger.info(f'QWebScreen: serving {self.url}')
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
        self._pool = ThreadPoolExecutor(
            1, thread_name_prefix='QWebScreen-camera')
        app = web.Application()
        app.router.add_get('/', self._index)
        app.router.add_get('/ws', self._socket)
        app.router.add_get('/session', self._check)
        app.router.add_get('/join/{code}', self._join)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, self.host, self.port,
                              ssl_context=self._tls).start()
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
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None
            self._valuesTimer = None
            self._heldValues = {}

    def _allowed(self, request) -> bool:
        return not self.access or self._viewerOf(request) is not None

    def _page(self, text: str, status: int = 200):
        return self._web.Response(text=text, status=status,
                                  content_type='text/html',
                                  headers={'Cache-Control': 'no-store'})

    async def _index(self, request):
        if not self._allowed(request):
            return self._page(DENIED, 401)
        return self._page(PAGE)

    async def _check(self, request):
        '''Tell the page whether it is still paired.'''
        status = 200 if self._allowed(request) else 401
        return self._web.Response(status=status,
                                  headers={'Cache-Control': 'no-store'})

    async def _join(self, request):
        '''Pair a browser: the address that the QR code holds.'''
        address = request.remote or ''
        if self._blocked(address):
            return self._page(EXPIRED, 429)
        code = request.match_info['code'].encode()
        ident = secrets.token_urlsafe(16)
        with self._guard:
            good = self._pairing and hmac.compare_digest(
                code, self._secret.encode())
            if good:
                # one code pairs one browser: a link that was read off the
                # network is spent already
                self._secret = secrets.token_urlsafe(16)
                self._sessions[ident] = _Viewer(
                    ident, address, request.headers.get('User-Agent', ''))
        if not good:
            self._fail(address)
            return self._page(EXPIRED, 403)
        self.viewersChanged.emit()
        self.codeChanged.emit()
        reply = self._web.HTTPFound('/')
        # Lax, not Strict: the scan comes from another app, and a browser
        # does not send a Strict cookie in a redirect that another site began.
        reply.set_cookie(_COOKIE, ident, max_age=_COOKIE_AGE, httponly=True,
                         samesite='Lax', secure=self.secure)
        raise reply

    async def _socket(self, request):
        viewer = self._viewerOf(request)
        if self.access and viewer is None:
            raise self._web.HTTPUnauthorized()
        origin = request.headers.get('Origin')
        if origin is not None and urlsplit(origin).netloc != request.host:
            raise self._web.HTTPForbidden()     # another site's page
        ws = self._web.WebSocketResponse(heartbeat=20.,
                                         max_msg_size=_MAX_MESSAGE)
        await ws.prepare(request)
        client = _Client(ws, viewer)
        self._clients.add(client)
        if viewer is not None:
            viewer.clients.add(client)
        self.clientsChanged.emit(len(self._clients))
        self.viewersChanged.emit()
        if self._last is not None:      # a new browser sees the last frame
            client.put(self._last)
        sender = asyncio.create_task(client.run())
        try:
            if self._camera is not None:        # no camera, no controls
                await self._hello(client)
            async for message in ws:
                if message.type == self._web.WSMsgType.TEXT:
                    await self._handle(client, message.data)
        finally:
            sender.cancel()
            self._clients.discard(client)
            if viewer is not None:
                viewer.clients.discard(client)
                if not viewer.clients:      # control ends with the page
                    self._release(viewer)
            self.clientsChanged.emit(len(self._clients))
            self.viewersChanged.emit()
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
        web.openPairing()
        print(f'Scan this code, or open {web.pairingUrl}  Ctrl-C stops.')
        try:
            from QVideo.lib._qrcode import terminal
            print(terminal(web.pairingUrl))
        except ImportError:
            pass
        app.exec()
        source.stop()
        web.stop()
        camera.close()


if __name__ == '__main__':  # pragma: no cover
    QWebScreen.example()
