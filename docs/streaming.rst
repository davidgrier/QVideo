Video in a web browser
======================

:class:`~QVideo.lib.QWebScreen.QWebScreen` serves the video of a source to
web browsers: a tablet at the bench, a phone, another computer.  It is the
counterpart of :class:`~QVideo.lib.QVideoScreen.QVideoScreen` for a viewer
that is not a Qt window, and the two can run at the same time on the same
source.

It needs ``aiohttp``::

    pip install "QVideo[stream]"

Using it
--------

::

    from QVideo.lib import QVideoSource
    from QVideo.lib.QWebScreen import QWebScreen

    source = QVideoSource(camera).start()
    web = QWebScreen(source).start()
    print(web.url)              # open this in the browser

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

.. warning::

   There is **no authentication**: anyone who can reach the port sees the
   video.  Use it on a trusted network (``host='127.0.0.1'`` serves this
   machine only).  The page only shows the video; it controls nothing.

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

A browser asks for ``/`` (the page) and then opens a WebSocket at ``/ws``.
The server sends **binary** messages and the page sends nothing yet.  A
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

What it does not do
-------------------

The page is for looking.  It has no controls and no touch interaction, no
overlays and no authentication, and it sends JPEG frames: video with H.264
would need much less bandwidth and is not supported.  The format leaves room
for overlays that are drawn over the frame and for events that the page sends
back.
