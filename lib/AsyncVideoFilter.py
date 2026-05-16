'''Async VideoFilter base for computationally expensive operations.'''
import weakref
from qtpy import QtCore
from QVideo.lib.QVideoFilter import VideoFilter
from QVideo.lib.videotypes import Image
import numpy as np


__all__ = ['AsyncVideoFilter']


class _AsyncWorker(QtCore.QObject):
    '''Runs filter.process in a background thread and reports the result.

    Holds a *weakref* to the owning filter rather than a bound method
    (``filter.process``).  A bound method would create a strong reference
    cycle — ``AsyncVideoFilter → _worker → _fn → AsyncVideoFilter`` — that
    Python's reference-counting GC cannot break.  PyQt5 uses weak references
    for signal-slot connections, so the ``destroyed`` and ``aboutToQuit``
    connections do *not* keep the filter alive; only the external reference
    from the rack does.  When the cyclic GC runs (triggered by any allocation
    that crosses the GC threshold, e.g. a mouse-move event), it detects the
    unreachable cycle and collects it, destroying ``_thread`` while it is
    still running and causing Qt to abort.  The weakref breaks the cycle so
    that Python's refcount mechanism handles collection instead, which fires
    ``destroyed`` reliably before ``_thread`` is freed.
    '''

    def __init__(self, filter_ref: 'weakref.ref[AsyncVideoFilter]') -> None:
        super().__init__()
        self._ref = filter_ref

    @QtCore.Slot(np.ndarray)
    def run(self, image: Image) -> None:
        f = self._ref()
        if f is None:
            return
        result = f.process(image)
        f = self._ref()      # re-check: process() may have released the GIL
        if f is not None:
            f._result = result
            f._ready = True


class AsyncVideoFilter(VideoFilter):

    '''VideoFilter base for computationally expensive operations.

    Runs :meth:`process` in a dedicated background
    :class:`~qtpy.QtCore.QThread` so that heavy computation does not
    block the GUI event loop.  The standard :meth:`add` / :meth:`get`
    interface is preserved with two behavioural differences:

    - **Drop-frame strategy**: :meth:`add` submits a frame to the
      worker only when the worker is idle.  If the worker is still
      processing the previous frame the incoming frame is discarded
      rather than queued, preventing unbounded latency build-up.
    - **Cached result**: :meth:`get` returns the result of the last
      *completed* :meth:`process` call.  Before any result is ready
      it returns the raw input frame as a passthrough so the pipeline
      always has something to display.

    Subclasses override :meth:`process` instead of :meth:`add` /
    :meth:`get`.  :meth:`process` runs on the worker thread; it may
    read instance attributes freely (the GIL makes Python reads safe)
    but must not write to them.

    Parameters
    ----------
    None.  Subclass constructors should call ``super().__init__()``
    after initialising any attributes that :meth:`process` will read,
    so the worker thread starts with a fully initialised object.
    '''

    _submit = QtCore.Signal(np.ndarray)

    def __init__(self) -> None:
        super().__init__()
        self._ready = True
        self._result: Image | None = None
        self._worker = _AsyncWorker(weakref.ref(self))
        self._thread = QtCore.QThread()
        self._worker.moveToThread(self._thread)
        self._submit.connect(self._worker.run)
        self._thread.start()
        self.destroyed.connect(self._cleanup)
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._cleanup)

    def process(self, image: Image) -> Image:
        '''Perform the heavy computation on *image*.

        Called in the background thread.  The default implementation
        is a passthrough; subclasses should override this method.

        Parameters
        ----------
        image : Image
            Input frame.

        Returns
        -------
        Image
            Processed frame.
        '''
        return image

    def add(self, image: Image) -> None:
        '''Cache *image* and submit it to the worker if idle.

        If the worker is busy the frame is dropped to prevent
        unbounded queue growth.

        Parameters
        ----------
        image : Image
            Input frame.
        '''
        self.data = image
        if self._ready:
            self._ready = False
            self._submit.emit(image)

    def get(self) -> Image | None:
        '''Return the most recently processed frame.

        Returns the cached result of the last completed :meth:`process`
        call.  If no result is available yet (before the first
        :meth:`process` completes), returns the raw input frame so
        the pipeline has something to display immediately.

        Returns
        -------
        Image or None
            Processed frame, raw input frame, or ``None`` if
            :meth:`add` has never been called.
        '''
        if self._result is not None:
            return self._result
        return self.data

    def shutdown(self) -> None:
        '''Stop the background thread synchronously.

        Called by the pipeline when this filter is removed.  Safe to
        call multiple times.
        '''
        self._cleanup()

    def _onResult(self, result: Image) -> None:
        self._result = result
        self._ready = True

    @QtCore.Slot()
    def _cleanup(self) -> None:
        if not self._thread.isRunning():
            return
        self._thread.quit()
        self._thread.wait()
