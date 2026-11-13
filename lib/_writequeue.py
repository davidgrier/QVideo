'''Queue requests to change camera settings in a separate thread.

GUI controls can request a camera to change its settings faster
than the camera can comply. Write requests block, causing the user
interface to lag. :class:`WriteQueue` keeps GUI controls responsive
by accepting a stream of write requests on behalf of the camera and
writing them to the camera when the camera unblocks. Only the most
recent request is kept for each camera setting, ensuring that write
requests do not pile up. The queue is maintained in a separate thread,
so that user controls remain responsive. The queue is thread-safe and
is compatible with any GUI framework, including Qt.
'''
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ['WriteQueue']

#: A batch: the latest ``(value, token)`` for each name, in order of arrival.
Batch = dict[str, tuple[Any, int]]


class WriteQueue:

    '''Write batches of values in a worker thread, keeping the
    latest value of each name.

    Parameters
    ----------
    work : callable
        Called in the worker thread with a batch, a ``dict`` of
        ``name: (value, token)``, in the order in which the names were last
        set.  The token is the caller's: here it counts the edits of a
        name.  An exception that *work* raises is logged, and the queue goes
        on.
    name : str
        The name of the worker thread.
    '''

    def __init__(self, work: Callable[[Batch], None],
                 name: str = 'WriteQueue') -> None:
        self._work = work
        self._name = name
        self._condition = threading.Condition()
        self._pending: Batch = {}
        self._busy = False
        self._closed = False
        self._thread: threading.Thread | None = None

    def put(self, key: str, value: Any, token: int = 0) -> None:
        '''Queue *value* for *key*, replacing one that is waiting.

        A name that is set again goes to the end, so that the writes keep the
        order in which the user last touched the names.  Does nothing once
        the queue is closed.
        '''
        with self._condition:
            if self._closed:
                return
            self._pending.pop(key, None)
            self._pending[key] = (value, token)
            if not self._busy:
                self._busy = True
                self._thread = threading.Thread(
                    target=self._run, name=self._name, daemon=True)
                self._thread.start()

    def idle(self) -> bool:
        '''Return whether nothing is waiting and nothing is being written.'''
        with self._condition:
            return not self._busy and not self._pending

    def wait(self, timeout: float | None = None) -> bool:
        '''Wait until the queue is idle; return whether it is.'''
        with self._condition:
            return self._condition.wait_for(
                lambda: not self._busy and not self._pending, timeout)

    def close(self) -> None:
        '''Drop what is waiting, wait for the write in progress, and refuse
        more.  Safe to call again, and from the worker thread.'''
        with self._condition:
            self._closed = True
            self._pending.clear()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()

    def _run(self) -> None:
        '''The worker: write what is waiting, until nothing is.'''
        while True:
            with self._condition:
                if not self._pending:
                    self._busy = False
                    self._condition.notify_all()
                    return
                batch, self._pending = self._pending, {}
            try:
                self._work(batch)
            except Exception:       # the queue must go on
                logger.exception(f'{self._name}: a write failed')
