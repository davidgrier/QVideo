'''The process that owns the camera of a :class:`QRemoteCamera`.

Run as ``python -m QVideo.lib._remoteworker KEY CAMERAID RPCFD FRAMEFD``.
It opens the camera of backend *KEY*, reads frames into a ring of shared
memory, and answers the requests of the proxy.  It never creates a
``QApplication``.  When the proxy goes away (the connection closes), it
closes the camera and exits.
'''
import errno
import importlib
import logging
import os
import socket
import sys
import threading
import time
from multiprocessing.connection import Connection
from multiprocessing.shared_memory import SharedMemory

import numpy as np

from QVideo.lib._remote import (CODES, EVENT, HEADER, NOTICE, REPLY, SLOTS,
                                slot_bytes)

logger = logging.getLogger('QVideo.remote.worker')

#: Seconds to close the camera before the process exits regardless.
EXIT_DEADLINE = 8.

#: Seconds between reports of a read that fails over and over.
ERROR_INTERVAL = 1.

#: Seconds between the pushes of the states of the watched nodes, and the
#: number of nodes in one push (a push reads them under one hold of the
#: camera lock, so it should be short).
PUSH_INTERVAL = 0.2
PUSH_CHUNK = 32

#: Seconds to wait after a failed read, so that a camera that fails at once
#: does not keep the process busy.
RETRY_DELAY = 0.01


class Worker:

    '''Reads frames from a camera into the ring and serves the proxy.

    One thread reads the camera; the thread that calls :meth:`serve`
    answers the requests of the proxy.  The camera serializes the two.
    Both send on the same connection, so every message goes through
    :meth:`send`, which lets one thread at a time write.

    Parameters
    ----------
    camera : QCamera
        The open camera.
    rpc : Connection
        Requests from the proxy, the answers to them and the events.
    frames : socket.socket
        Datagram socket on which the frames are announced.
    '''

    def __init__(self, camera, rpc: Connection, frames: socket.socket):
        self.camera = camera
        self.rpc = rpc
        self.frames = frames
        self.frames.setblocking(False)
        self.running = True
        self.ring: SharedMemory | None = None
        self.generation = 0
        self.capacity = 0
        self.count = 0
        self.failures = 0
        self.reported = -ERROR_INTERVAL
        self.announced = self.shape()
        self.watched: list[str] = []
        self.cursor = 0
        self.pushed = 0.
        self.writing = threading.Lock()
        self.thread = threading.Thread(target=self.capture, daemon=True)

    # ------------------------------------------------------------------
    # What the worker says
    # ------------------------------------------------------------------

    def send(self, message: tuple) -> None:
        '''Send *message* to the proxy, one thread at a time.'''
        with self.writing:
            self.rpc.send(message)

    def reply(self, ok: bool, value) -> None:
        '''Answer the request that the proxy is waiting on.'''
        self.send((REPLY, ok, value))

    def notify(self, kind: str, payload) -> None:
        '''Tell the proxy something that no request asked for.

        The proxy may be gone already, which is then nobody's concern.
        '''
        try:
            self.send((EVENT, kind, payload))
        except (EOFError, OSError):
            pass

    # ------------------------------------------------------------------
    # The ring
    # ------------------------------------------------------------------

    def allocate(self, nbytes: int) -> None:
        '''Make a ring whose slots hold frames of *nbytes*.'''
        old = self.ring
        self.capacity = slot_bytes(nbytes)
        self.ring = SharedMemory(create=True, size=SLOTS * self.capacity)
        self.ring.buf[:] = bytes(self.ring.size)
        self.generation += 1
        if old is not None:
            old.close()
            old.unlink()

    def publish(self, frame: np.ndarray) -> None:
        '''Put *frame* in the next slot of the ring and announce it.'''
        frame = np.ascontiguousarray(frame)
        if frame.dtype not in CODES:
            raise TypeError(f'frames of {frame.dtype} are not supported')
        nbytes = frame.nbytes
        if self.ring is None or slot_bytes(nbytes) > self.capacity:
            self.allocate(nbytes)
        height, width = frame.shape[:2]
        if (width, height) != self.announced:
            # Whoever changed the shape, the proxy hears of it before the
            # first frame of the new shape.
            self.announced = (width, height)
            self.notify('shape', self.announced)
        self.count += 1
        slot = self.count % SLOTS
        start = slot * self.capacity
        header = np.ndarray(1, np.uint64, self.ring.buf, start)
        header[0] = 0
        pixels = np.ndarray(frame.shape, frame.dtype, self.ring.buf,
                            start + HEADER)
        pixels[...] = frame
        header[0] = self.count
        h, w = frame.shape[:2]
        channels = frame.shape[2] if frame.ndim == 3 else 0
        stamp = getattr(self.camera, 'hardwareTimestamp', None)
        notice = NOTICE.pack(self.count, self.generation, slot, h, w,
                             channels, CODES[frame.dtype],
                             float('nan') if stamp is None else stamp)
        try:
            self.frames.send(notice)
        except BlockingIOError:     # the reader is behind: it skips ahead
            pass
        except OSError as ex:
            if ex.errno != errno.ENOBUFS:       # macOS: the queue is full
                raise

    def capture(self) -> None:
        '''Read the camera until told to stop; publish every frame.'''
        while self.running:
            try:
                ok, frame = self.camera.saferead()
                if ok:
                    self.publish(frame)
            except Exception as ex:
                self.failed(ex)
            self.push()

    def watch(self, names) -> None:
        '''Push the states of the nodes *names*, a few at a time, between
        frames, so that the proxy need not ask for them.'''
        self.watched = list(names)
        self.cursor = 0

    def push(self) -> None:
        '''Send the states of the next few watched nodes, if it is time.

        The capture thread calls it after a frame, so the interface never
        waits for the camera to read the nodes.
        '''
        names = self.watched
        now = time.monotonic()
        if not names or now - self.pushed < PUSH_INTERVAL:
            return
        self.pushed = now
        if self.cursor >= len(names):
            self.cursor = 0
        chunk = names[self.cursor:self.cursor + PUSH_CHUNK]
        self.cursor += PUSH_CHUNK
        try:
            self.notify('states', self.camera.states(chunk))
        except Exception:
            logger.exception('reading the watched states failed')

    def failed(self, ex: Exception) -> None:
        '''Report a failure to read or to publish a frame.

        Call it from the ``except`` block, so that the log has the traceback.
        A camera that fails over and over is reported once in
        :data:`ERROR_INTERVAL`, with the number of failures since.
        '''
        self.failures += 1
        now = time.monotonic()
        if now - self.reported >= ERROR_INTERVAL:
            self.reported = now
            logger.exception('read failed')
            self.notify('error', f'{type(ex).__name__}: {ex}'
                        f' ({self.failures} failures)')
            self.failures = 0
        time.sleep(RETRY_DELAY)

    # ------------------------------------------------------------------
    # The requests
    # ------------------------------------------------------------------

    def describe(self) -> dict:
        '''Describe the camera for the proxy: its properties and methods.'''
        camera = self.camera
        properties = {}
        for name, spec in camera.properties.items():
            meta = {k: v for k, v in spec.items()
                    if k not in ('getter', 'setter', 'ptype')}
            properties[name] = dict(ptype=spec['ptype'].__name__,
                                    writable=spec['setter'] is not None,
                                    meta=meta)
        return dict(name=camera.name,
                    modelName=camera.model_name,
                    properties=properties,
                    methods=camera.methods,
                    aliases=dict(camera.aliases))

    def shape(self) -> tuple[int, int]:
        '''Return the shape of the frames as ``(width, height)``.'''
        size = self.camera.shape
        return size.width(), size.height()

    def ringInfo(self) -> tuple:
        '''Return the name, slot size and generation of the ring.'''
        return self.ring.name, self.capacity, self.generation

    def serve(self) -> None:
        '''Answer the requests of the proxy until it closes or goes away.'''
        camera = self.camera
        handlers = dict(
            describe=self.describe,
            get=camera.get,
            settings=lambda: camera.settings,
            actualFps=lambda: camera.actualFps,
            shape=self.shape,
            ring=self.ringInfo,
            watch=self.watch,
            execute=camera.execute)
        # What a tree of a GenICam camera asks for, as plain data.
        for name in ('nodeTree', 'hasNode', 'states'):
            if hasattr(camera, name):
                handlers[name] = getattr(camera, name)
        while True:
            try:
                op, args = self.rpc.recv()
            except (EOFError, OSError):
                return
            try:
                if op == 'close':
                    self.reply(True, None)
                    return
                if op == 'set':
                    camera.set(*args)
                    value = self.shape()
                elif op == 'apply':
                    camera.settings = args[0]
                    value = self.shape()
                else:
                    value = handlers[op](*args)
                self.reply(True, value)
            except Exception as ex:
                logger.exception(f'{op} failed')
                try:
                    self.reply(False, f'{type(ex).__name__}: {ex}')
                except (EOFError, OSError):
                    return

    def stop(self) -> None:
        '''Stop reading, close the camera and release the ring.'''
        self.running = False
        deadline = threading.Timer(EXIT_DEADLINE, os._exit, (0,))
        deadline.daemon = True          # it must not keep the process alive
        deadline.start()
        if self.thread.is_alive():
            self.thread.join()
        try:
            self.camera.close()
        finally:
            if self.ring is not None:
                self.ring.close()
                self.ring.unlink()


def main(argv: list[str]) -> int:
    '''Open the camera named on the command line and serve it.

    Returns
    -------
    int
        The exit code of the process: 0, or 1 if the camera did not open.
    '''
    key, cameraID, rpcfd, framefd = argv
    rpc = Connection(int(rpcfd))
    frames = socket.socket(fileno=int(framefd))
    try:
        from QVideo.cameras.chooser import BACKENDS
        if ':' in key:                      # 'module:Class'
            modulename, classname = key.split(':')
        else:
            entry = BACKENDS[key]
            modulename, classname = entry.module, entry.camera_cls
        module = importlib.import_module(modulename)
        camera = getattr(module, classname)(cameraID=int(cameraID))
        camera.open()
        if not camera.isOpen():
            raise RuntimeError(f'{classname} did not open')
    except Exception as ex:
        logger.exception('cannot open the camera')
        rpc.send((REPLY, False, f'{type(ex).__name__}: {ex}'))
        return 1
    worker = Worker(camera, rpc, frames)
    worker.reply(True, None)
    worker.thread.start()
    try:
        worker.serve()
    finally:
        worker.stop()
        frames.close()
        rpc.close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
