'''Unit tests for QFilterPipeline.'''
import inspect
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
from qtpy import QtCore, QtTest, QtWidgets
from QVideo.lib.QFilterPipeline import QFilterPipeline
from QVideo.lib.QFilterRackWidget import QFilterRackWidget
from QVideo.lib.QVideoFilter import QVideoFilter, VideoFilter
from QVideo.lib.videotypes import FrameInfo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Source(QtCore.QObject):
    '''Stands in for a QVideoSource.'''
    newFrame = QtCore.Signal(np.ndarray, object)
    shapeChanged = QtCore.Signal(QtCore.QSize)
    fps = 30.
    shape = QtCore.QSize(4, 4)

    def send(self, index: int) -> FrameInfo:
        info = FrameInfo(index, float(index))
        self.newFrame.emit(np.full((4, 4), index, dtype=np.uint8), info)
        return info


class _Add(VideoFilter):
    def __init__(self, n):
        super().__init__()
        self.n = n

    def __call__(self, image):
        return image + self.n


class _Gate(VideoFilter):
    '''Blocks inside the worker until released; records what it saw.'''

    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()
        self.seen = []
        self.thread = None

    def __call__(self, image):
        self.thread = QtCore.QThread.currentThread()
        self.seen.append(int(image[0, 0]))
        self.started.set()
        self.release.wait(3.)
        return image


class _Boom(VideoFilter):
    def __call__(self, image):
        raise ValueError('boom')


class _Nothing(VideoFilter):
    def __call__(self, image):
        return None


def wait_until(condition, timeout=3.):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        QtTest.QTest.qWait(5)
    return condition()


class PipelineTestCase(unittest.TestCase):

    def make(self, filters=(), **kwargs):
        self.source = _Source()
        self.pipeline = QFilterPipeline(self.source, filters, **kwargs)
        self.out = []
        self.pipeline.newFrame.connect(
            lambda frame, info: self.out.append((int(frame[0, 0]), info)))
        self.addCleanup(self.pipeline.stop)
        return self.pipeline

    def values(self):
        return [value for value, _ in self.out]


class TestPassThrough(PipelineTestCase):

    def test_frames_pass_through_with_no_filters(self):
        self.make()
        self.source.send(5)
        self.assertTrue(wait_until(lambda: self.out))
        self.assertEqual(self.values(), [5])

    def test_info_is_the_one_the_source_emitted(self):
        self.make()
        info = self.source.send(7)
        self.assertTrue(wait_until(lambda: self.out))
        self.assertIs(self.out[0][1], info)

    def test_frames_keep_their_order(self):
        self.make()
        for i in range(3):
            self.source.send(i)
            self.assertTrue(wait_until(lambda i=i: len(self.out) == i + 1))
        self.assertEqual(self.values(), [0, 1, 2])


class TestFilters(PipelineTestCase):

    def test_filters_apply_in_order(self):
        class Double(VideoFilter):
            def __call__(self, image):
                return image * 2
        self.make([_Add(1), Double()])
        self.source.send(3)
        self.assertTrue(wait_until(lambda: self.out))
        self.assertEqual(self.values(), [8])          # (3 + 1) * 2

    def test_filters_run_off_the_calling_thread(self):
        gate = _Gate()
        gate.release.set()
        self.make([gate])
        self.source.send(1)
        self.assertTrue(wait_until(lambda: self.out))
        self.assertIsNot(gate.thread, QtCore.QThread.currentThread())

    def test_replacing_the_filters_takes_effect_on_the_next_frame(self):
        self.make([_Add(1)])
        self.source.send(1)
        self.assertTrue(wait_until(lambda: len(self.out) == 1))
        self.pipeline.filters = [_Add(10)]
        self.source.send(1)
        self.assertTrue(wait_until(lambda: len(self.out) == 2))
        self.assertEqual(self.values(), [2, 11])

    def test_filters_property_returns_the_active_filters(self):
        add = _Add(1)
        self.make([add])
        self.assertEqual(self.pipeline.filters, (add,))

    def test_a_filter_returning_none_emits_nothing(self):
        self.make([_Nothing()])
        self.source.send(1)
        QtTest.QTest.qWait(100)
        self.assertEqual(self.out, [])


class TestBusyWorker(PipelineTestCase):
    '''What happens to frames that arrive while the worker is busy.'''

    def _busy(self, depth):
        gate = _Gate()
        self.make([gate], depth=depth)
        self.dropped = []
        self.pipeline.framesDropped.connect(self.dropped.append)
        self.source.send(0)
        self.assertTrue(gate.started.wait(2.))
        return gate

    def test_default_depth_keeps_only_the_latest_frame(self):
        gate = self._busy(depth=1)
        for i in range(1, 5):
            self.source.send(i)
        gate.release.set()
        self.assertTrue(wait_until(lambda: len(self.out) == 2))
        self.assertEqual(self.values(), [0, 4])

    def test_dropped_frames_are_counted_and_signalled(self):
        gate = self._busy(depth=1)
        for i in range(1, 5):
            self.source.send(i)
        gate.release.set()
        self.assertTrue(wait_until(lambda: sum(self.dropped) == 3))

    def test_deeper_queue_keeps_the_newest_frames_that_fit(self):
        gate = self._busy(depth=3)
        for i in range(1, 6):
            self.source.send(i)
        gate.release.set()
        self.assertTrue(wait_until(lambda: len(self.out) == 4))
        self.assertEqual(self.values(), [0, 3, 4, 5])
        self.assertEqual(sum(self.dropped), 2)

    def test_no_drops_when_the_worker_keeps_up(self):
        self.make()
        self.dropped = []
        self.pipeline.framesDropped.connect(self.dropped.append)
        for i in range(5):
            self.source.send(i)
            self.assertTrue(wait_until(lambda i=i: len(self.out) == i + 1))
        self.assertEqual(self.dropped, [])


class TestFailure(PipelineTestCase):

    def test_failed_filter_is_reported(self):
        boom = _Boom()
        self.make([boom])
        failures = []
        self.pipeline.filterFailed.connect(
            lambda f, error: failures.append((f, error)))
        self.source.send(1)
        self.assertTrue(wait_until(lambda: failures))
        self.assertIs(failures[0][0], boom)
        self.assertIsInstance(failures[0][1], ValueError)

    def test_frame_passes_through_the_failed_filter(self):
        self.make([_Add(1), _Boom(), _Add(10)])
        self.pipeline.filterFailed.connect(lambda f, e: None)
        self.source.send(1)
        self.assertTrue(wait_until(lambda: self.out))
        self.assertEqual(self.values(), [12])        # 1 + 1 (skip) + 10

    def test_failed_filter_is_removed_and_reported_once(self):
        boom = _Boom()
        self.make([boom])
        failures = []
        self.pipeline.filterFailed.connect(lambda f, e: failures.append(f))
        for i in range(3):
            self.source.send(i)
            self.assertTrue(wait_until(lambda i=i: len(self.out) == i + 1))
        self.assertEqual(len(failures), 1)
        self.assertNotIn(boom, self.pipeline.filters)

    def test_failure_is_logged_with_the_filter_name(self):
        self.make([_Boom()])
        with self.assertLogs('QVideo.lib.QFilterPipeline',
                             level='ERROR') as cm:
            self.source.send(1)
            self.assertTrue(wait_until(lambda: self.out))
        self.assertIn('_Boom', cm.output[0])


class TestSourceInterface(PipelineTestCase):
    '''The pipeline can stand in for a QVideoSource.'''

    def test_fps_comes_from_the_source(self):
        self.make()
        self.assertEqual(self.pipeline.fps, 30.)

    def test_shape_comes_from_the_source(self):
        self.make()
        self.assertEqual(self.pipeline.shape, QtCore.QSize(4, 4))

    def test_shape_changes_are_forwarded(self):
        self.make()
        seen = []
        self.pipeline.shapeChanged.connect(seen.append)
        self.source.shapeChanged.emit(QtCore.QSize(8, 6))
        self.assertEqual(seen, [QtCore.QSize(8, 6)])

    def test_changing_the_source_reroutes_frames(self):
        self.make()
        other = _Source()
        self.pipeline.source = other
        self.source.send(1)
        other.send(2)
        self.assertTrue(wait_until(lambda: self.out))
        QtTest.QTest.qWait(50)
        self.assertEqual(self.values(), [2])


class TestRack(PipelineTestCase):
    '''A pipeline follows the enabled filters of a QFilterRackWidget.'''

    def setUp(self):
        self.rack = QFilterRackWidget()
        self.widgets = []
        for n in (1, 10):
            widget = QVideoFilter(None, f'+{n}', _Add(n))
            widget.setChecked(True)
            self.rack.add(widget)
            self.widgets.append(widget)

    def pipeline_with_rack(self, **kwargs):
        pipeline = self.make(rack=self.rack, **kwargs)
        return pipeline

    def test_starts_with_the_checked_filters(self):
        pipeline = self.pipeline_with_rack()
        self.assertEqual(pipeline.filters,
                         tuple(w.filter for w in self.widgets))

    def test_toggling_a_filter_updates_the_pipeline(self):
        pipeline = self.pipeline_with_rack()
        self.widgets[0].setChecked(False)
        self.assertEqual(pipeline.filters, (self.widgets[1].filter,))

    def test_adding_a_filter_updates_the_pipeline(self):
        pipeline = self.pipeline_with_rack()
        extra = QVideoFilter(None, 'extra', _Add(100))
        extra.setChecked(True)
        self.rack.add(extra)
        self.assertEqual(pipeline.filters[-1], extra.filter)

    def test_frames_are_filtered_by_the_rack_filters(self):
        self.pipeline_with_rack()
        self.source.send(1)
        self.assertTrue(wait_until(lambda: self.out))
        self.assertEqual(self.values(), [12])             # 1 + 1 + 10

    def test_failed_filter_switches_its_widget_off(self):
        boom = QVideoFilter(None, 'boom', _Boom())
        boom.setChecked(True)
        self.rack.add(boom)
        pipeline = self.pipeline_with_rack()
        self.source.send(1)
        self.assertTrue(wait_until(lambda: not boom.isChecked()))
        self.assertIn('boom', boom.toolTip())
        self.assertNotIn(boom.filter, pipeline.filters)

    def test_rechecking_a_failed_filter_puts_it_back(self):
        boom = QVideoFilter(None, 'boom', _Boom())
        boom.setChecked(True)
        self.rack.add(boom)
        pipeline = self.pipeline_with_rack()
        self.source.send(1)
        self.assertTrue(wait_until(lambda: not boom.isChecked()))
        boom.setChecked(True)
        self.assertIn(boom.filter, pipeline.filters)

    def test_detaching_the_rack_stops_following_it(self):
        pipeline = self.pipeline_with_rack()
        pipeline.rack = None
        before = pipeline.filters
        self.widgets[0].setChecked(False)
        self.assertEqual(pipeline.filters, before)


class TestNoSource(PipelineTestCase):

    def test_source_can_be_cleared(self):
        self.make()
        self.pipeline.source = None
        self.source.send(1)
        QtTest.QTest.qWait(50)
        self.assertEqual(self.out, [])
        self.assertIsNone(self.pipeline.source)

    def test_source_can_be_set_again_after_clearing(self):
        self.make()
        self.pipeline.source = None
        self.pipeline.source = self.source
        self.source.send(3)
        self.assertTrue(wait_until(lambda: self.out))
        self.assertEqual(self.values(), [3])


class TestDroppingAStack(unittest.TestCase):
    """Dropping the last reference to a running pipeline must not abort Qt
    ("QThread: Destroyed while thread is still running")."""

    CODE = """
import os, gc
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import numpy as np
from qtpy import QtCore, QtWidgets
app = QtWidgets.QApplication([])
from QVideo.lib import QFilterPipeline


class Source(QtCore.QObject):
    newFrame = QtCore.Signal(np.ndarray, object)
    shapeChanged = QtCore.Signal(QtCore.QSize)


def build():
    pipeline = QFilterPipeline(Source())
    assert pipeline.isRunning()


build()
gc.collect()
print('survived')
"""

    def test_dropping_a_running_pipeline_is_safe(self):
        result = subprocess.run([sys.executable, '-c', self.CODE],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        self.assertIn('survived', result.stdout)
        self.assertNotIn('Destroyed while thread', result.stderr)

    def test_a_pipeline_takes_no_parent(self):
        """A parent would let Qt delete the running thread."""
        parameters = inspect.signature(QFilterPipeline).parameters
        self.assertNotIn('parent', parameters)

    def test_a_failed_construction_is_quiet(self):
        code = ("import os\n"
                "os.environ['QT_QPA_PLATFORM'] = 'offscreen'\n"
                "from qtpy import QtWidgets\n"
                "app = QtWidgets.QApplication([])\n"
                "from QVideo.lib import QFilterPipeline\n"
                "try:\n    QFilterPipeline()\n"
                "except TypeError:\n    pass\n"
                "import gc; gc.collect(); print('done')\n")
        result = subprocess.run([sys.executable, '-c', code],
                                capture_output=True, text=True)
        self.assertIn('done', result.stdout)
        self.assertNotIn('Exception ignored', result.stderr)


class TestLifecycle(PipelineTestCase):

    def test_finalizer_ignores_a_deleted_thread(self):
        pipeline = self.make()
        with patch.object(QFilterPipeline, 'isRunning',
                          side_effect=RuntimeError):
            pipeline.__del__()
        self.assertTrue(pipeline.isRunning())

    def test_thread_is_running_after_creation(self):
        self.make()
        self.assertTrue(self.pipeline.isRunning())

    def test_stop_ends_the_thread(self):
        self.make()
        self.pipeline.stop()
        self.assertFalse(self.pipeline.isRunning())

    def test_stop_is_idempotent(self):
        self.make()
        self.pipeline.stop()
        self.pipeline.stop()
        self.assertFalse(self.pipeline.isRunning())

    def test_frames_after_stop_are_ignored(self):
        self.make()
        self.pipeline.stop()
        self.source.send(1)
        QtTest.QTest.qWait(50)
        self.assertEqual(self.out, [])

    def test_stop_while_a_filter_is_busy_does_not_hang(self):
        gate = _Gate()
        self.make([gate])
        self.source.send(1)
        self.assertTrue(gate.started.wait(2.))
        gate.release.set()
        self.pipeline.stop()
        self.assertFalse(self.pipeline.isRunning())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
