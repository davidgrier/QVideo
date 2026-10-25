'''Unit tests for QFrameRelay.'''
import gc
import threading
import unittest
import numpy as np
from qtpy import QtCore, QtWidgets
from QVideo.lib.QFrameRelay import QFrameRelay
from QVideo.lib.videotypes import FrameInfo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Source(QtCore.QObject):
    newFrame = QtCore.Signal(np.ndarray, object)


class _PlainSource(QtCore.QObject):
    newFrame = QtCore.Signal(np.ndarray)


def frame(n: int) -> np.ndarray:
    return np.full((2, 2), n, dtype=np.uint8)


def emit_from_thread(source, indices):
    '''Emit frames from a thread other than the one running the relay.'''
    def run():
        for n in indices:
            source.newFrame.emit(frame(n), FrameInfo(n, float(n)))
    thread = threading.Thread(target=run)
    thread.start()
    thread.join()


class RelayTestCase(unittest.TestCase):

    def make(self, source=None):
        self.source = source or _Source()
        self.relay = QFrameRelay(self.source)
        self.out = []
        self.relay.newFrame.connect(
            lambda image, info: self.out.append((int(image[0, 0]), info)))
        return self.relay

    def values(self):
        return [value for value, _ in self.out]


class TestDelivery(RelayTestCase):

    def test_a_frame_arrives(self):
        self.make()
        emit_from_thread(self.source, [1])
        app.processEvents()
        self.assertEqual(self.values(), [1])

    def test_the_info_arrives_unchanged(self):
        self.make()
        emit_from_thread(self.source, [4])
        app.processEvents()
        self.assertEqual(self.out[0][1], FrameInfo(4, 4.))

    def test_a_one_argument_source_gives_no_info(self):
        source = _PlainSource()
        self.make(source)
        source.newFrame.emit(frame(1))
        app.processEvents()
        self.assertEqual(self.out, [(1, None)])

    def test_frames_in_the_receiving_thread_arrive_at_once(self):
        self.make()
        self.source.newFrame.emit(frame(1), FrameInfo(1, 1.))
        self.source.newFrame.emit(frame(2), FrameInfo(2, 2.))
        self.assertEqual(self.values(), [1, 2])


class TestLatestWins(RelayTestCase):

    def test_a_busy_receiver_gets_only_the_newest_frame(self):
        self.make()
        emit_from_thread(self.source, range(50))
        app.processEvents()
        self.assertEqual(self.values(), [49])

    def test_the_receiver_is_woken_once_while_it_is_busy(self):
        self.make()
        wakes = []
        self.relay._wake.connect(lambda: wakes.append(1))
        emit_from_thread(self.source, range(50))
        app.processEvents()
        self.assertEqual(len(wakes), 1)

    def test_the_next_frame_is_delivered_after_a_pickup(self):
        self.make()
        emit_from_thread(self.source, range(5))
        app.processEvents()
        emit_from_thread(self.source, range(5, 10))
        app.processEvents()
        self.assertEqual(self.values(), [4, 9])

    def test_nothing_is_delivered_twice(self):
        self.make()
        emit_from_thread(self.source, [1])
        app.processEvents()
        app.processEvents()
        self.assertEqual(self.values(), [1])


class TestLifetime(RelayTestCase):

    def test_a_deleted_relay_receives_nothing_and_raises_nothing(self):
        self.make()
        del self.relay
        gc.collect()
        emit_from_thread(self.source, [1])
        app.processEvents()
        self.assertEqual(self.out, [])


if __name__ == '__main__':
    unittest.main()
