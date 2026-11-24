'''What the proxy and the worker of a remote camera agree on.

This is the whole protocol.  A person who writes a backend, or fixes a bug in
:class:`~QVideo.lib.remote.camera.QRemoteCamera`, should not need to read the
code to learn it.

**Two channels.**  The proxy (in the program) starts the worker with
``python -m QVideo.lib.remote KEY CAMERAID RPCFD FRAMEFD`` and passes it the
two ends of two Unix sockets.  *KEY* is a key of
:data:`QVideo.cameras.chooser.BACKENDS`, or ``module:Class``.

``rpc``
    A stream connection (:class:`multiprocessing.connection.Connection`)
    that carries pickled tuples both ways: the requests, the answers, and the
    events.
``frames``
    A datagram socket on which the worker announces each frame.  A datagram is
    atomic, and a reader that is slow loses announcements, never the stream.

The frames themselves are in a ring of shared memory.

**Requests and answers.**  The proxy sends ``(op, args)`` and waits for the
answer, one request at a time.  The worker answers with ``(REPLY, ok, value)``:
*value* is the result if *ok* is true, and the text ``'ErrorType: message'`` if
it is not, which the proxy raises as a
:class:`~QVideo.lib.errors.QCameraError`.  The worker handles a request in the
thread that serves, while another thread reads the camera, and the camera
serializes the two, so a request waits for the frame that is being read.
The requests are

``describe``
    The name and model of the camera, the aliases, the methods, and for each
    property its type (``bool``, ``int``, ``float`` or ``str``), whether it can
    be written, and its metadata (which must be picklable).
``get`` *name*, ``set`` *name* *value*, ``settings``, ``apply`` *settings*
    A property, and all of them.  ``set`` and ``apply`` answer with the
    shape of the frames, ``(width, height)``, which the setting may have
    changed.
``execute`` *name*
    A method of the camera.
``shape``, ``actualFps``
    The shape of the frames, and the frame rate that the camera delivers.
``watch`` *names*
    Ask for the changes of those properties on the camera's own account (see
    ``changes`` below).
``nodeTree``, ``hasNode`` *name*, ``states`` *names*
    What the tree of a GenICam camera asks for, as plain data.  The worker
    answers them if its camera has them.
``ring``
    Where the ring is: its name, the size of a slot, and its generation.  It
    fails until the camera has delivered a frame, because the ring is made for
    the first frame.
``close``
    Close the camera and end the worker.

An unknown request is answered as a failure.  The first message of the worker
is not an answer to a request but the answer to the proxy's wait for it to
open the camera: ``(REPLY, True, None)``, or ``(REPLY, False, message)`` and
the worker ends with exit code 1.  The proxy waits ``QRemoteCamera.OPENING``
seconds for it.

**Events.**  ``(EVENT, kind, payload)`` is something that the worker says on
its own, at any time.  The proxy listens in a thread of its own and sorts the
events from the answers.

``changes`` *dict*
    Watched properties that the camera changed itself (an automatic exposure
    that settled).  The proxy emits ``propertiesChanged``.
``shape`` *(width, height)*
    The frames have a new shape.  It is sent ahead of the first frame of the
    new shape, whoever changed it, so a frame never arrives in a shape that
    the proxy has not been told.  The proxy emits ``shapeChanged``.
``lost`` *reason*
    The camera has gone (``_deviceLost``).  The next read of the proxy makes
    it lost here too.
``error`` *message*
    A read or a publication failed.  The worker sends one for every second of
    failures, with their number.  The proxy logs it.

**The ring.**  ``SLOTS`` slots of equal size, in one block of shared memory.
Frame number *n* (the worker counts from 1) goes in slot ``n % SLOTS``, which
starts at ``slot * capacity``.  A slot has ``HEADER`` bytes, of which the first
eight are the number of the frame that the slot holds (a little-endian
unsigned integer; zero while the worker is writing it), and then the pixels,
C-contiguous, ``(height, width)`` for a gray image and
``(height, width, channels)`` for a color one, ``uint8`` or ``uint16``.  A
frame of any other type is a failure, reported as an event.  The worker makes
the ring for the first frame, and makes a larger one, with the next
*generation*, when a frame does not fit; it never makes a smaller one.  It
closes and unlinks the old ring at once.

**The announcement** of a frame is a datagram of ``NOTICE`` (56 bytes, little
endian): the number of the frame, the generation of the ring, the slot, the
height, the width, the channels (0 for a gray image), the code of the dtype
(0 for ``uint8``, 1 for ``uint16``), the hardware timestamp [s], and the black
and white levels of the pixels.  The timestamp and the levels are NaN where the
camera has none.

**Reading a frame** (``read``). The proxy waits up to ``QRemoteCamera.TIMEOUT``
for an announcement and, if one comes, takes every announcement that is waiting
and uses the last. If its generation is not the one that the proxy knows, the
proxy asks the worker where the ring is and attaches to it. It copies the slot
out of the ring and then looks at the number in the header of the slot: if it
is not the number that was announced, the worker has begun to overwrite the
slot and the copy is thrown away.

**What is guaranteed about frames.**  A frame that ``read`` returns was not
overwritten while it was copied, as far as the number in the header of its slot
shows (the check has no memory barrier: it relies on the order in which the
processor makes the writes of the worker visible, and on the worker being
``SLOTS`` frames ahead before it comes back to a slot).  The frames that it
returns are in order, and each is newer than the one before.

**What is not.**  Every frame.  The worker never waits for the proxy: if the
proxy is slower than the camera, it skips ahead to the newest frame, and the
frames in between are lost.  (A camera in the program hands over the frames of
its driver's queue, late, and that is not what the proxy does.)  Nor is the
delay of a frame guaranteed: it has the time of an announcement and of a copy.
A read that finds no frame, or a frame that was overwritten before it was
copied, returns ``(False, None)``, as a camera in the program does when a read
fails.

**The life of the worker.**

*Start.*  The proxy makes the sockets, starts the process, and waits for the
first message.  Then it asks for ``describe`` and ``shape``.  On Windows the
proxy refuses to start, because there is no file descriptor to give to a
child.

*Close.*  The proxy sends ``close``; the worker answers, stops reading, closes
the camera, closes and unlinks the ring, and exits with code 0.  The proxy
waits ten seconds for the process and then kills it.  A worker that takes
longer than ``EXIT_DEADLINE`` seconds to close the camera exits regardless.

*Death of the program.*  When the connection closes, the worker closes the
camera and the ring as it does for ``close``, and exits.

*Death of the worker* (a crash of the vendor's library, or a kill).  The
connection closes, so a request that is waiting fails with a
:class:`~QVideo.lib.errors.QCameraError`, and so does every request after it.
The proxy remembers that the camera is lost, with the exit code of the process,
and the next read closes the proxy and emits ``lost``, as a camera in the
program does.  Nothing waits.
'''
import struct
import numpy as np

__all__ = ['SLOTS', 'HEADER', 'NOTICE', 'DTYPES', 'CODES', 'REPLY', 'EVENT',
           'slot_bytes']

#: Tag of a message that answers a request.
REPLY = 'reply'

#: Tag of a message that the worker sends on its own.
EVENT = 'event'

#: Frames in the ring: the writer is this far ahead of a slow reader before
#: it overwrites a frame that is not yet read.
SLOTS = 4

#: Bytes before the pixels of every slot: the number of the frame that the
#: slot holds (zero while it is being written).
HEADER = 64

#: Announcement of a frame: number, generation of the ring, slot, height,
#: width, channels (0 for a gray image), dtype code, hardware timestamp,
#: black level and white level (NaN where the camera has none).
NOTICE = struct.Struct('<QIIIIIIddd')

DTYPES = {0: np.dtype(np.uint8), 1: np.dtype(np.uint16)}
CODES = {dtype: code for code, dtype in DTYPES.items()}


def slot_bytes(nbytes: int) -> int:
    '''Return the size of a slot for a frame of *nbytes*.'''
    return HEADER + nbytes
