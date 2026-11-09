Video in a web browser
======================

:class:`~QVideo.lib.QWebScreen.QWebScreen` serves the video of a source to
web browsers: a tablet at the bench, a phone, another computer.  It is the
counterpart of :class:`~QVideo.lib.QVideoScreen.QVideoScreen` for a viewer
that is not a Qt window, and the two can run at the same time on the same
source.

It needs ``aiohttp`` and ``segno`` (which draws the QR code)::

    pip install "QVideo[stream]"

Using it
--------

::

    from QVideo.lib import QVideoSource
    from QVideo.lib.QWebScreen import QWebScreen

    source = QVideoSource(camera).start()
    web = QWebScreen(source).start()

    from QVideo.widgets import QWebShareDialog
    share = QWebShareDialog(web)
    share.show()                # the QR code that pairs a tablet

To show what the filters make, connect it to the pipeline, as for a screen:
``web.source = rack.pipeline``.  ``python -m QVideo.demos.webdemo`` shows the
window and the web page together, and says where to find the page.
``python -m QVideo.lib.QWebScreen -g`` serves a camera and nothing else.

The page is one small file that fits the video to the window.  Tapping it
hides the frame readout.  Several browsers can watch at once, and a browser
that is closed or loses the connection reconnects by itself.

A frame of more than 8 bits is shown between the levels that it comes with,
as the screen does (``levels``, ``autoLevels``).  ``maxWidth`` (1024),
``quality`` (70) and ``framerate`` (30) trade picture for bandwidth: at 1280
by 1024 a typical frame is about 130 KB (31 Mb/s at 30 frames a second) at
quality 80 and about 65 KB at quality 60, and a noisy one is several times
larger.

.. note::

   By default the connection is **not encrypted** (see
   :ref:`streaming-encryption`).  Use it on a trusted network, or give the
   server a certificate.  A page can change camera properties only with the
   operator's permission (:ref:`streaming-control`).

Pairing a tablet
----------------

A browser sees nothing until the instrument pairs it.  The program shows
:class:`~QVideo.widgets.QWebShareDialog.QWebShareDialog` (a button, a menu
item or a shortcut calls its ``toggle()``; the web demo has a Share button
and Ctrl+Shift+W).  While that window is open it shows a QR code, and the
camera of a tablet or phone opens the address in it.  The server answers
with a cookie, and from then on that browser sees the video.

The idea is that **only people who can see the screen of the instrument
can watch**, and that the window is a *pairing window*:

* the code works only while the window is open, and **pairs one browser**:
  the secret changes after each pairing and the window shows the new code,
  so an address that was read off the network is already spent.  Closing
  the window changes the secret too, so a photograph of the code, or a
  screen that was shared, pairs nothing afterward;
* a paired browser stays paired (for a week, if the browser keeps the
  cookie, and until the program ends) and reconnects without a new scan;
* the window lists the paired browsers.  **Disconnect** removes one, and
  **Disconnect all** every one; **New code** changes the secret while the
  window stays open;
* a few wrong codes a minute from one address block it for a minute, and
  the secret has 128 random bits, so it cannot be guessed;
* a page from another web site cannot open the video stream of a paired
  browser.

Without a window, ``web.openPairing()`` and ``web.closePairing()`` do the
same, ``web.pairingUrl`` is the address, ``web.viewers`` lists the paired
browsers and ``web.revoke(id)`` removes one.
``python -m QVideo.lib.QWebScreen -g`` opens pairing and prints the QR code
in the terminal.  ``QWebScreen(access=False)`` turns pairing off, for a
machine that only you can reach.

A tablet that adds the page to its home screen may keep its cookies apart
from the browser that scanned the code: scan from the home-screen page, or
scan again.

.. _streaming-encryption:

Encryption
----------

There are three levels, and a program picks the one that its network needs.

**Plain http (the default).**  Nothing to install and nothing to set.
Pairing keeps strangers out: the code works for one browser, while the
window is open.  But anyone who can read the network traffic sees the video
and the cookie, so use it on a network whose users you trust.  This is
enough for looking at a microscope on a tablet.  The window says "Not
encrypted".

**https with a certificate that you provide.**  ``QWebScreen(source,
certfile='cert.pem', keyfile='key.pem')`` serves https (TLS 1.2 or later),
the address begins with ``https://``, the cookie is ``Secure``, and the
window says "Encrypted".  The certificate must name the host that the
browser uses, and the browser must trust it; that is the hard part.  In
the order that I would try them:

* **Tailscale.**  Install it on both devices, then ``tailscale cert
  <name>.<tailnet>.ts.net`` writes a certificate that every browser trusts,
  and the address is that name.
* **A certificate from your institution** for a host name of the instrument.
* **A private certificate authority**, such as ``mkcert``.  Install its root
  certificate on each device (on an iPad: install the profile, then trust
  it under Settings, General, About, Certificate Trust Settings).
* **A reverse proxy** (Caddy or nginx) that ends TLS and can add logins:
  QVideo listens on ``host='127.0.0.1'`` behind it.

A self-signed certificate is for testing: a browser warns, and some do not
allow a WebSocket to it.

**External certification.**  A proxy or an identity-aware gateway in front
of QVideo, which authenticates people itself.  QVideo's pairing then adds
nothing and ``access=False`` is reasonable.

Controls from the page need the second level (or a proxy): a cookie that
was read off the network must not move a laser.  A program that trusts its
network as it trusts the instrument can opt out with
``controlOverHttp=True``.

.. _streaming-control:

Controls from the page
----------------------

Pairing lets a browser *look*.  Given the camera, the page can also *change*
it::

    web = QWebScreen(source, camera=camera, certfile=..., keyfile=...)

The page then has a Controls button.  Its panel builds a control for each
property from the :class:`~QVideo.lib.QCamera.PropertySpec` of the camera: a
slider for a number with limits (logarithmic when the range spans three
decades, as an exposure does), a switch for a ``bool``, a drop-down for a
choice, and a number box for a number without limits.  The values follow the
camera, including a gain or exposure that it changes by itself, and a change
made in the window of the instrument (the Qt tree) shows on the page.

**The operator decides.**  The panel starts view only.  *Ask to control*
raises a prompt on the screen of the instrument (from
:class:`~QVideo.widgets.QWebShareDialog.QWebShareDialog`, whether or not it
is showing): *Allow* or *Deny*.  A browser that was refused waits a few
seconds before it can ask again.  One browser controls at a time; granting
another takes control from the first, and so does *Take back control* in the
window.  Control ends by itself when the page closes.  A program that has no
dialog connects ``web.controlRequested`` to ``web.grantControl`` or
``web.denyControl``.

**What a page can change.**  ``properties=['exposure', 'gain']`` names them.
By default they are the usual ones that the camera has and lets us write
(exposure, gain, gamma, brightness, contrast, saturation, black and white
level, frame rate), and ``properties=[]`` turns control off.  The server
checks every value again and does not trust the page: an unlisted property
or a read-only one cannot be set, a number is clipped to the limits of the
property, a choice must be one of its choices, and anything else (a string
for a number, ``NaN``) is ignored.

**Where it is available.**  Control needs a certificate (https), or
``controlOverHttp=True``, and pairing (``access=True``).  Otherwise the panel
says "View only" and why, and so does the window of the instrument.

How it works
------------

The server runs in a thread of its own.  The newest frame of the source is
kept (a frame that has not been encoded when the next arrives is dropped),
scaled, converted to 8 bits and encoded as JPEG, once for all browsers and
not at all while there are none.  Each browser has a mailbox of one message:
a slow browser gets the newest frame and skips the rest, and never slows the
camera or another browser.  A browser that connects sees the last frame at
once.

The protocol
------------

A browser pairs with ``/join/<secret>``, which sets a cookie and redirects
to ``/``.  It then asks for ``/`` (the page) and opens a WebSocket at
``/ws``; ``/session`` answers 200 while the browser is paired and 401 if
not.  The server closes the WebSocket with code 4401 when the instrument
disconnects the browser.  The server sends **binary** messages, one for each
frame, and **text** messages (JSON, below) about the controls.  A binary
message holds one frame and everything that belongs to it:

======== ============= ====================================================
Bytes    Content       Meaning
======== ============= ====================================================
0 to 3   ``n``         length of the header, an unsigned 32 bit integer, big
                       endian
4 to n+3 header        UTF-8 JSON, below
n+4 on   picture       a JPEG
======== ============= ====================================================

The header has these keys:

``version``
    ``1``.  A reader ignores keys that it does not know.
``index``
    the index of the frame (:class:`~QVideo.lib.videotypes.FrameInfo`):
    a gap means that frames were dropped on the way.
``time``
    the capture time on the host [s] (``time.perf_counter``, an arbitrary
    zero).
``width``, ``height``
    the size of the frame before it was scaled; the picture can be smaller.
``levels``
    the black and white levels of the frame, or ``null``.
``overlays``
    reserved for what is drawn over the frame, in the coordinates of
    ``width`` by ``height``; empty for now.  It travels in the message of the
    frame, so an overlay is always drawn on the frame that it describes.

The page is also the specification of a client: another program can read the
same messages.

The text messages are JSON objects with a ``type``.  The server sends:

``hello``
    on connecting, when there is a camera: ``controls`` (a list of
    ``name``, ``type`` (``bool``, ``int``, ``float`` or ``list``), ``value``,
    ``writable`` and, where the camera says, ``min``, ``max``, ``step`` and
    ``limits``), ``available``, ``reason`` (why it is not) and ``state``.
``control``
    ``state`` (``none``, ``requested``, ``granted``, ``denied`` or
    ``revoked``), ``available`` and ``reason``.
``values``
    ``values``: the exposed properties that changed.

The page sends ``{"type": "request"}``, ``{"type": "release"}`` and
``{"type": "set", "name": ..., "value": ...}``; the last is ignored unless
the operator has granted control.  A message of more than 4 KB closes the
connection.

What it does not do
-------------------

The page controls the camera but nothing else, and it has no touch
interaction with overlays and no encryption unless the program gives a
certificate.  It sends JPEG frames: video with H.264 would need much less
bandwidth and is not supported.  The format leaves room for overlays that
are drawn over the frame and for events that the page sends back.
