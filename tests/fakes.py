'''Stand-ins for sources, writers and readers, shared by the DVR tests.'''
import threading
from pathlib import Path
import numpy as np
from qtpy import QtCore, QtTest
from QVideo.lib import QVideoReader
from QVideo.lib.videotypes import FrameInfo

_FRAME = np.zeros((4, 4), dtype=np.uint8)

#: The sample video in the documentation (a source checkout has it).
EXAMPLE_VIDEO = str(
    Path(__file__).resolve().parent.parent / 'docs' / 'diatom3.avi')


def until(condition, ms=5000):
    for _ in range(ms // 10):
        if condition():
            return True
        QtTest.QTest.qWait(10)
    return False


class FakeSource(QtCore.QObject):
    '''A source that emits frames when it is told to.'''
    newFrame = QtCore.Signal(np.ndarray, object)

    def __init__(self, fps=30.):
        super().__init__()
        self.fps = fps

    def emit(self, n=1, first=0):
        for i in range(first, first + n):
            self.newFrame.emit(_FRAME, FrameInfo(i, 10. + i / 30.))


class FakeWriter(QtCore.QObject):
    '''Behaves like a QVideoWriter, and keeps a note of what it did.'''
    finished = QtCore.Signal(str)
    frameNumber = QtCore.Signal(int)
    made: list = []

    def __init__(self, filename, fps=24., nframes=10, nskip=1):
        super().__init__()
        self.filename, self.fps = filename, fps
        self.target, self.nskip = nframes, nskip
        self.received = None
        self.written = 0
        self.closed = False
        self.threads = set()
        FakeWriter.made.append(self)

    @QtCore.Slot(np.ndarray, object)
    def write(self, frame, info=None):
        self.threads.add(threading.current_thread())
        if self.written >= self.target:
            self.finished.emit('')
            return
        self.written += 1
        self.frameNumber.emit(self.written)

    @QtCore.Slot()
    def shutdown(self):
        self.closed = True
        self.thread().quit()


class FakeReader(QVideoReader):
    '''A reader of frames that are filled with their own index.'''
    LENGTH = 10
    opens = True

    def __init__(self, filename):
        self._n = 0
        super().__init__(filename)

    def _initialize(self):
        return self.opens

    def _deinitialize(self):
        pass

    def read(self):
        if self._n >= self.LENGTH:
            return False, None
        self._n += 1
        return True, np.full((2, 2), (self._n - 1) % 256, np.uint8)

    def seek(self, framenumber):
        self._n = framenumber

    fps = property(lambda self: 200.)
    length = property(lambda self: self.LENGTH)
    framenumber = property(lambda self: self._n)
    width = property(lambda self: 2)
    height = property(lambda self: 2)
