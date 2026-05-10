'''Async VideoFilter base for computationally expensive operations.'''
from collections.abc import Callable
from qtpy import QtCore
from QVideo.lib.QVideoFilter import VideoFilter
from QVideo.lib.videotypes import Image
import numpy as np


__all__ = ['AsyncVideoFilter']


class _AsyncWorker(QtCore.QObject):
    '''Runs a callable in a background thread and emits the result.'''

    resultReady = QtCore.Signal(np.ndarray)

    def __init__(self, fn: Callable[[Image], Image]) -> None:
        super().__init__()
        self._fn = fn

    @QtCore.Slot(np.ndarray)
    def run(self, image: Image) -> None:
        self.resultReady.emit(self._fn(image))


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
        self._worker = _AsyncWorker(self.process)
        self._thread = QtCore.QThread()
        self._worker.moveToThread(self._thread)
        self._submit.connect(self._worker.run)
        self._worker.resultReady.connect(self._onResult)
        self._thread.start()
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

    @QtCore.Slot(np.ndarray)
    def _onResult(self, result: Image) -> None:
        self._result = result
        self._ready = True

    @QtCore.Slot()
    def _cleanup(self) -> None:
        self._thread.quit()
        self._thread.wait()
