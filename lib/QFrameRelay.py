'''Latest-frame handoff from a capture thread to the thread of a consumer.'''
import numpy as np
from qtpy import QtCore
from QVideo.lib.videotypes import Image, FrameInfo


__all__ = ['QFrameRelay']


class QFrameRelay(QtCore.QObject):

    '''Pass the newest frame of a source to the thread this object lives in.

    A queued connection delivers every frame, so while the receiving thread
    is busy (a modal dialog, a window drag, heavy painting) the frames wait
    in its event queue without limit: three seconds of a 200 fps, 2048 x 2048
    camera hold 1.5 GB.  The relay keeps one frame instead.  A frame that
    arrives before the previous one was taken replaces it, and the receiving
    thread is woken at most once, so its event queue stays short and it
    always gets the latest frame.

    Use it for consumers that only show or sample the stream.  A consumer
    that needs every frame, such as a recorder, connects to the source.

    The relay is the receiver of ``source.newFrame`` through a direct
    connection, so it runs in the capture thread and never blocks it.  It
    lives in the thread that created it; frames with the same
    :class:`~QVideo.lib.videotypes.FrameInfo` the source emitted arrive in
    that thread.  A consumer behind a relay sees gaps in ``info.index`` where
    frames were replaced.

    Parameters
    ----------
    source : QVideoSource
        Provider of ``newFrame(ndarray, FrameInfo)``, or of
        ``newFrame(ndarray)``.

    Signals
    -------
    newFrame(ndarray, FrameInfo)
        The newest frame since the previous emission.
    '''

    newFrame = QtCore.Signal(np.ndarray, object)
    _wake = QtCore.Signal()

    def __init__(self, source) -> None:
        super().__init__()
        self._mutex = QtCore.QMutex()
        self._latest: tuple[Image, FrameInfo | None] | None = None
        self._wake.connect(self._deliver)
        source.newFrame.connect(self._offer, QtCore.Qt.DirectConnection)

    @QtCore.Slot(np.ndarray)
    @QtCore.Slot(np.ndarray, object)
    def _offer(self, frame: Image, info: FrameInfo | None = None) -> None:
        '''Keep *frame*; runs in the thread that emitted ``newFrame``.'''
        with QtCore.QMutexLocker(self._mutex):
            idle, self._latest = self._latest is None, (frame, info)
        if idle:
            self._wake.emit()

    @QtCore.Slot()
    def _deliver(self) -> None:
        '''Pass the kept frame on; runs in the thread of the relay.'''
        with QtCore.QMutexLocker(self._mutex):
            frame, info = self._latest
            self._latest = None
        self.newFrame.emit(frame, info)
