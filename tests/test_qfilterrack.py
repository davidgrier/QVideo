'''Unit tests for QFilterRack: a rack widget that owns a pipeline.'''
import time
import unittest
import numpy as np
from qtpy import QtCore, QtTest, QtWidgets
from QVideo.lib import QFilterPipeline, QFilterRack, QFilterRackWidget
from QVideo.lib.QVideoFilter import QVideoFilter, VideoFilter
from QVideo.lib.videotypes import FrameInfo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Source(QtCore.QObject):
    '''Stands in for a QVideoSource.'''
    newFrame = QtCore.Signal(np.ndarray, object)
    shapeChanged = QtCore.Signal(QtCore.QSize)
    fps = 30.
    shape = QtCore.QSize(4, 4)

    def send(self, index: int) -> None:
        frame = np.full((4, 4), index, dtype=np.uint8)
        self.newFrame.emit(frame, FrameInfo(index, float(index)))


class _Add(VideoFilter):
    def __init__(self, n):
        super().__init__()
        self.n = n

    def __call__(self, image):
        return image + self.n


def wait_until(condition, timeout=3.):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        QtTest.QTest.qWait(5)
    return condition()


class RackTestCase(unittest.TestCase):

    def make(self, **kwargs) -> QFilterRack:
        rack = QFilterRack(**kwargs)
        self.addCleanup(rack.pipeline.stop)
        return rack


class TestStructure(RackTestCase):

    def test_is_a_rack_widget(self):
        self.assertIsInstance(self.make(), QFilterRackWidget)

    def test_owns_a_running_pipeline(self):
        rack = self.make()
        self.assertIsInstance(rack.pipeline, QFilterPipeline)
        self.assertTrue(rack.pipeline.isRunning())

    def test_the_pipeline_follows_the_rack(self):
        rack = self.make()
        self.assertIs(rack.pipeline.rack, rack)

    def test_without_a_source_the_pipeline_is_idle(self):
        self.assertIsNone(self.make().pipeline.source)

    def test_parent_and_editable_keep_their_positions(self):
        parent = QtWidgets.QWidget()
        rack = self.make(parent=parent, editable=False)
        self.assertIs(rack.parent(), parent)
        self.assertFalse(rack.editable)

    def test_depth_reaches_the_pipeline(self):
        rack = self.make(depth=8)
        self.assertEqual(rack.pipeline._queue.maxlen, 8)


class TestSource(RackTestCase):

    def test_the_constructor_gives_the_pipeline_its_source(self):
        source = _Source()
        self.assertIs(self.make(source=source).pipeline.source, source)

    def test_source_reads_and_sets_the_pipeline_source(self):
        rack = self.make()
        source = _Source()
        rack.source = source
        self.assertIs(rack.pipeline.source, source)
        self.assertIs(rack.source, source)


class TestFiltering(RackTestCase):

    def test_frames_pass_through_the_switched_on_filters(self):
        source = _Source()
        rack = self.make(source=source)
        widget = QVideoFilter(None, '+5', _Add(5))
        widget.setChecked(True)
        rack.add(widget)
        out = []
        rack.pipeline.newFrame.connect(
            lambda frame, info: out.append(int(frame[0, 0])))
        source.send(1)
        self.assertTrue(wait_until(lambda: out))
        self.assertEqual(out, [6])

    def test_a_pipeline_of_your_own_still_works(self):
        source = _Source()
        rack = self.make()
        own = QFilterPipeline(source, rack=rack)
        self.addCleanup(own.stop)
        widget = QVideoFilter(None, '+5', _Add(5))
        widget.setChecked(True)
        rack.add(widget)
        out = []
        own.newFrame.connect(
            lambda frame, info: out.append(int(frame[0, 0])))
        source.send(1)
        self.assertTrue(wait_until(lambda: out))
        self.assertEqual(out, [6])


class TestShutdown(RackTestCase):

    def test_deleting_the_rack_stops_the_pipeline(self):
        parent = QtWidgets.QWidget()
        rack = self.make(parent=parent)
        pipeline = rack.pipeline
        parent.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        self.assertFalse(pipeline.isRunning())

    def test_quitting_the_application_stops_the_pipeline(self):
        rack = self.make()
        app.aboutToQuit.emit()
        self.assertFalse(rack.pipeline.isRunning())

    def test_closing_a_window_only_hides_the_rack(self):
        parent = QtWidgets.QWidget()
        rack = self.make(parent=parent)
        parent.show()
        parent.close()
        self.assertTrue(rack.pipeline.isRunning())


class TestWidgetStaysThreadFree(unittest.TestCase):

    def test_the_widget_alone_starts_no_thread(self):
        self.assertFalse(hasattr(QFilterRackWidget(), 'pipeline'))


if __name__ == '__main__':
    unittest.main()
