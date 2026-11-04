'''A camera in a process of its own.

Some camera libraries hold the interpreter lock while they wait for a
frame (the ``genicam`` binding of Harvesters), and a program that uses
one freezes its interface.  :class:`QRemoteCamera` runs such a camera in
a worker process and looks like any other :class:`~QVideo.lib.QCamera`.

The package has three parts:

``camera``
    :class:`QRemoteCamera`, the proxy in the program.  It starts the worker,
    sends the requests and reads the frames.
``worker``
    The program that the proxy starts (``python -m QVideo.lib.remote``).
    It opens the camera, reads frames into a ring of shared memory and
    answers the proxy.
``protocol``
    What the two agree on: the layout of the ring, the datagram that
    announces a frame, and the tags of the messages.

Nothing outside this package uses ``worker`` or ``protocol``.
'''
from .camera import QRemoteCamera


__all__ = ['QRemoteCamera']
