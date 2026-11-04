'''What the proxy and the worker of a remote camera agree on.

The two processes share a ring of frames in shared memory.  A frame is
announced by a datagram on a socket of its own (a datagram is atomic, and a
reader that is slow loses announcements, never the stream).  Everything
else, such as settings, goes over a connection that answers every request.

Everything that the worker sends on that connection is a tuple that begins
with a tag.  ``(REPLY, ok, value)`` answers the request that the proxy sent,
and the proxy waits for it.  ``(EVENT, kind, payload)`` is something that
the worker says on its own, at any time, such as a failure that no request
caused.  The proxy listens in a thread of its own and sorts the two apart.
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
#: width, channels (0 for a gray image), dtype code, hardware timestamp.
NOTICE = struct.Struct('<QIIIIIId')

DTYPES = {0: np.dtype(np.uint8), 1: np.dtype(np.uint16)}
CODES = {dtype: code for code, dtype in DTYPES.items()}


def slot_bytes(nbytes: int) -> int:
    '''Return the size of a slot for a frame of *nbytes*.'''
    return HEADER + nbytes
