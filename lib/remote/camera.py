'''A camera that runs in a process of its own.'''
import contextlib
import logging
import queue
import socket
import subprocess
import sys
import threading
from multiprocessing.connection import Connection
from multiprocessing.shared_memory import SharedMemory

import numpy as np
from qtpy import QtCore

from QVideo.lib.remote.protocol import DTYPES, EVENT, HEADER, NOTICE, REPLY
from QVideo.lib.errors import QCameraError
from QVideo.lib.QCamera import QCamera

logger = logging.getLogger(__name__)

__all__ = ['QRemoteCamera']

PTYPES = {'bool': bool, 'int': int, 'float': float, 'str': str}


class QRemoteCamera(QCamera):

    '''Proxy for a camera that runs in a process of its own.

    Another process opens the camera of the backend *key*, reads its
    frames and holds whatever the vendor's library holds, such as the
    interpreter lock.  This object looks like the camera: it has its
    properties and methods, and it is a :class:`QCamera`, so a
    :class:`~QVideo.lib.QVideoSource` and a
    :class:`~QVideo.lib.QCameraTree` use it as they use any other.
    Reading a frame waits on a socket, which does not hold the interpreter.

    A thread of this object listens to the worker, so that the worker can
    say something when nobody has asked: that a read failed, that it has
    gone.  A failure goes to the log, with the message of the worker.

    It is available on macOS and Linux.  On Windows opening it raises
    :exc:`~QVideo.lib.errors.QCameraError`.

    Parameters
    ----------
    key : str
        Key of the backend in ``QVideo.cameras.chooser.BACKENDS``.
    cameraID : int
        Index of the camera.  Default: ``0``.
    python : str, optional
        Interpreter of the worker.  Default: this one.
    only : list of str, optional
        Names of the properties to offer.  Default: all of them.
    '''

    #: How long to wait for a frame before :meth:`read` returns [s].
    TIMEOUT = 0.1
    #: How long to wait for the worker to open the camera [s].
    OPENING = 30.
    #: How long to wait for the listener to end after the worker [s].
    LISTENING = 2.

    #: None: the worker is the authority on the shape and announces it
    #: (:meth:`_changed`), and reading the shape here would take round trips.
    shapeProperties = ()

    def __init__(self, key: str, *args,
                 cameraID: int = 0,
                 python: str | None = None,
                 only: list[str] | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._key = key
        self._cameraID = cameraID
        self._python = python or sys.executable
        self._only = only
        self._process: subprocess.Popen | None = None
        self._rpc: Connection | None = None
        self._frames: socket.socket | None = None
        self._lock = threading.RLock()
        self._replies: queue.Queue = queue.Queue()
        self._reader: threading.Thread | None = None
        self._ended = False
        self._closing = False
        self._opened = False
        self._events = {'error': self._onError, 'changes': self._onChanges,
                        'shape': self._changed}
        self._shapeLock = threading.Lock()
        self._ring: SharedMemory | None = None
        self._generation = -1
        self._capacity = 0
        self._remoteName = 'QRemoteCamera'
        self._shape = (0, 0)
        self._lost = False
        self.open()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _initialize(self) -> bool:
        '''Start the worker, wait for it to open the camera and copy its
        properties and methods.'''
        if sys.platform == 'win32':
            raise QCameraError('A camera in a process of its own is not '
                               'available on Windows yet')
        self._ended = self._closing = self._opened = False
        self._replies = queue.Queue()
        rpc, theirRpc = socket.socketpair()
        frames, theirFrames = socket.socketpair(socket.AF_UNIX,
                                                socket.SOCK_DGRAM)
        command = [self._python, '-m', 'QVideo.lib.remote',
                   self._key, str(self._cameraID),
                   str(theirRpc.fileno()), str(theirFrames.fileno())]
        self._process = subprocess.Popen(
            command, pass_fds=[theirRpc.fileno(), theirFrames.fileno()])
        theirRpc.close()
        theirFrames.close()
        self._rpc = Connection(rpc.detach())
        frames.settimeout(self.TIMEOUT)
        self._frames = frames
        self._reader = threading.Thread(target=self._listen,
                                        args=(self._rpc, self._replies),
                                        daemon=True)
        self._reader.start()
        try:
            ok, message = self._receive(self.OPENING)
        except queue.Empty:
            ok, message = False, 'it did not answer'
        except EOFError:
            ok, message = False, 'the worker died'
        if not ok:
            self._kill()
            self._release()
            raise QCameraError(f'Cannot open the {self._key} camera: '
                               f'{message}')
        self._opened = True
        self._register(self._call('describe'))
        self._shape = tuple(self._call('shape'))
        return True

    def _register(self, description: dict) -> None:
        self._remoteName = description['name']
        self._modelName = description['modelName']
        self.aliases = description['aliases']
        for name, spec in description['properties'].items():
            if self._only is not None and name not in self._only:
                continue
            setter = (self._setter(name) if spec['writable'] else None)
            self.registerProperty(name,
                                  getter=self._getter(name),
                                  setter=setter,
                                  ptype=PTYPES[spec['ptype']],
                                  **spec['meta'])
        for name in description['methods']:
            self.registerMethod(name, self._executor(name))

    def _getter(self, name: str):
        return lambda: self._call('get', name)

    def _setter(self, name: str):
        def setter(value):
            self._changed(self._call('set', name, value))
        return setter

    def _executor(self, name: str):
        def execute():
            self._call('execute', name)
            self._changed(self._call('shape'))
        return execute

    def _deinitialize(self) -> None:
        self._closing = True            # the end of the worker is expected
        with contextlib.suppress(QCameraError, EOFError, OSError):
            self._call('close')
        process = self._process
        if process is not None:
            try:
                process.wait(10.)
            except subprocess.TimeoutExpired:
                self._kill()
        self._release()

    def _kill(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.kill()
            self._process.wait()

    def _release(self) -> None:
        if self._reader is not None:    # it ends when the worker has gone
            self._reader.join(self.LISTENING)
            self._reader = None
        if self._ring is not None:
            self._ring.close()
            self._ring = None
        for end in (self._rpc, self._frames):
            if end is not None:
                end.close()
        self._rpc = self._frames = None
        self._process = None
        self._generation = -1       # the next worker makes a ring of its own
        self._lost = False

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    def _call(self, op: str, *args):
        '''Ask the worker to do *op* and return what it answers.'''
        try:
            with self._lock:
                if self._ended or self._rpc is None:
                    raise EOFError
                self._rpc.send((op, args))
                ok, value = self._receive()
        except (EOFError, OSError) as ex:
            raise QCameraError(f'The {self._key} camera process '
                               f'has ended ({op})') from ex
        if not ok:
            raise QCameraError(f'{self._remoteName}.{op}: {value}')
        return value

    def _receive(self, timeout: float | None = None) -> tuple:
        '''Return the next answer of the worker as ``(ok, value)``.

        Raises
        ------
        queue.Empty
            If *timeout* passes first.
        EOFError
            If the worker has gone.
        '''
        reply = self._replies.get(timeout=timeout)
        if reply is None:
            raise EOFError
        return reply

    def _listen(self, rpc: Connection, replies: queue.Queue) -> None:
        '''Sort what the worker sends until it goes.

        An answer waits in *replies* for the request that asked for it.
        An event is handled here, in this thread.
        '''
        while True:
            try:
                tag, *message = rpc.recv()
            except (EOFError, OSError):
                break
            if tag == REPLY:
                replies.put(message)
            elif tag == EVENT:
                self._handle(*message)
            else:
                logger.warning(f'The {self._key} camera process sent {tag}')
        self._ended = True
        replies.put(None)               # wake the request that waits
        self._gone()

    def _handle(self, kind: str, payload) -> None:
        '''Pass an event of the worker to the method that handles *kind*.'''
        handler = self._events.get(kind)
        if handler is None:
            logger.warning(f'The {self._key} camera process sent '
                           f'the event {kind}')
            return
        try:
            handler(payload)
        except Exception:
            logger.exception(f'Handling the event {kind} failed')

    def _onChanges(self, values: dict) -> None:
        '''Pass on the properties that the camera changed by itself.'''
        self.propertiesChanged.emit(values)

    def _onError(self, message: str) -> None:
        logger.error(f'{self._remoteName}: {message}')

    def _gone(self) -> None:
        '''Say so, once, if an open camera's worker ended unasked.

        A worker that never opened its camera is not a loss: opening fails
        with its own message.  Neither is the end that :meth:`close` asks for.
        '''
        process = self._process
        if self._closing or not self._opened or process is None:
            return
        try:
            code = process.wait(self.LISTENING)
        except subprocess.TimeoutExpired:
            code = 'not known'
        self._lost = True
        logger.error(f'The {self._key} camera process ended '
                     f'with code {code}')

    def _changed(self, shape) -> None:
        '''Announce a shape that the worker reported, if it is new.

        The worker is the authority: it reports the shape in the answer to
        a request and, whoever changed the shape (a request, or the camera
        itself), in a ``shape`` event ahead of the first frame of the new
        shape.  The shape of a frame that the proxy reads is not: frames of
        the old shape are still on their way for a while after a change.
        The listener thread and the caller of a request both come here.
        '''
        shape = tuple(shape)
        with self._shapeLock:
            if shape == self._shape:
                return
            self._shape = shape
        self.shapeChanged.emit(QtCore.QSize(*shape))

    @property
    def name(self) -> str:
        '''Name of the class of the camera in the worker.'''
        return self._remoteName

    @property
    def settings(self) -> QCamera.Settings:
        '''All property values, in one request.'''
        return self._call('settings')

    @settings.setter
    def settings(self, settings: QCamera.Settings) -> None:
        self._changed(self._call('apply', settings))

    def nodeTree(self) -> dict:
        '''Return the node map of the camera as plain data.'''
        return self._call('nodeTree')

    def hasNode(self, name: str) -> bool:
        '''Return ``True`` if the camera has the node *name*.'''
        return self._call('hasNode', name)

    def watch(self, names) -> None:
        '''Name the nodes whose changes on their own are wanted.

        The worker's camera reports them (``propertiesChanged``), and the
        proxy emits the same signal.
        '''
        self._call('watch', list(names))

    def states(self, names) -> dict:
        '''Return snapshots of the nodes *names*, read in one request,
        which waits for the frame in progress.'''
        return self._call('states', list(names))

    @property
    def actualFps(self) -> float:
        '''Frame rate that the camera delivers [frames per second].'''
        return self._call('actualFps')

    # ------------------------------------------------------------------
    # Frames
    # ------------------------------------------------------------------

    def saferead(self) -> QCamera.CameraData:
        '''Read the newest frame.  The worker serializes the camera, so
        this does not hold the lock of the proxy while it waits.'''
        return self.read()

    def read(self) -> QCamera.CameraData:
        '''Wait for a frame and return the newest one.

        Returns ``(False, None)`` if none comes within :attr:`TIMEOUT`,
        so that the caller can look at whether it should go on.
        '''
        if self._frames is None:
            return False, None
        try:
            notice = self._frames.recv(NOTICE.size)
        except OSError:                     # timed out, or the worker went
            return False, None
        self._frames.settimeout(0.)         # skip to the newest
        try:
            while True:
                try:
                    notice = self._frames.recv(NOTICE.size)
                except OSError:
                    break
        finally:
            self._frames.settimeout(self.TIMEOUT)
        return self._copy(*NOTICE.unpack(notice))

    def _copy(self, number, generation, slot, h, w, channels, code,
              stamp, black, white) -> QCamera.CameraData:
        '''Copy the frame that a notice announces out of the ring.

        Returns ``(False, None)`` if the worker has gone, or has
        overwritten the frame before the copy was done.
        '''
        ring = self._ring
        if ring is None or generation != self._generation:
            try:
                name, self._capacity, self._generation = self._call('ring')
            except QCameraError as ex:      # the worker has gone
                logger.warning(f'No ring for the frame: {ex}')
                return False, None
            if ring is not None:
                ring.close()
            ring = self._ring = _attach(name)
        shape = (h, w, channels) if channels else (h, w)
        start = slot * self._capacity
        header = np.ndarray(1, np.uint64, ring.buf, start)
        frame = np.ndarray(shape, DTYPES[code], ring.buf,
                           start + HEADER).copy()
        if header[0] != number:             # overwritten while we copied
            return False, None
        self.hardwareTimestamp = None if np.isnan(stamp) else stamp
        self.levels = None if np.isnan(black) else (black, white)
        return True, frame

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self.close()


def _attach(name: str) -> SharedMemory:
    '''Attach to the ring of the worker, which unlinks it.'''
    try:
        return SharedMemory(name=name, track=False)  # pyright: ignore[reportCallIssue]
    except TypeError:                       # before Python 3.13
        ring = SharedMemory(name=name)
        from multiprocessing import resource_tracker
        resource_tracker.unregister(
            ring._name, 'shared_memory')  # pyright: ignore[reportAttributeAccessIssue]
        return ring
