'''Unit tests for QBacklogMonitor.'''
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from qtpy import QtWidgets
from QVideo.dvr.QBacklogMonitor import QBacklogMonitor
from QVideo.lib.videotypes import FrameInfo
from QVideo.tests.signals import record


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((4, 4), dtype=np.uint8)


class FakeWriter:
    '''Has taken up the frame that is stamped t=10.'''

    def __init__(self):
        self.received = FrameInfo(0, 10.)


class TestQBacklogMonitor(unittest.TestCase):

    def watching(self, **limits):
        self.writer = FakeWriter()
        monitor = QBacklogMonitor()
        monitor.start(self.writer, 30., **limits)
        self.fractions = record(monitor.backlog)
        self.lags = record(monitor.behind)
        return monitor

    def capture(self, monitor, t):
        monitor.check(_FRAME, FrameInfo(1, t))

    def test_a_writer_keeping_up_reports_nothing(self):
        monitor = self.watching()
        self.capture(monitor, 10.)
        self.assertEqual((self.fractions, self.lags), ([], []))

    def test_a_writer_ahead_of_the_capture_reports_nothing(self):
        monitor = self.watching()
        self.capture(monitor, 9.)
        self.assertEqual((self.fractions, self.lags), ([], []))

    def test_the_backlog_is_a_fraction_of_the_allowance(self):
        monitor = self.watching()
        self.capture(monitor, 10.5)
        self.assertEqual(self.fractions, [(0.5,)])
        self.assertEqual(self.lags, [])

    def test_the_backlog_is_reported_in_steps(self):
        monitor = self.watching()
        for t in (10.46, 10.48, 10.5):  # all within one 5% step
            self.capture(monitor, t)
        self.assertEqual(len(self.fractions), 1)
        self.capture(monitor, 10.6)
        self.assertEqual(len(self.fractions), 2)

    def test_falling_behind_is_reported_with_the_lag(self):
        monitor = self.watching()
        self.capture(monitor, 12.)
        self.assertEqual(self.lags, [(2.,)])

    def test_staying_behind_is_reported_once(self):
        monitor = self.watching()
        for t in (12., 12.1, 12.2):
            self.capture(monitor, t)
        self.assertEqual(self.lags, [(2.,)])

    def test_catching_up_rearms_the_report(self):
        monitor = self.watching()
        self.capture(monitor, 12.)
        self.writer.received = FrameInfo(1, 12.)
        self.capture(monitor, 12.1)
        self.capture(monitor, 14.)
        self.assertEqual(len(self.lags), 2)

    def test_catching_up_is_reported(self):
        monitor = self.watching()
        self.capture(monitor, 10.8)
        self.writer.received = FrameInfo(1, 10.8)
        self.capture(monitor, 10.85)
        self.assertEqual(len(self.fractions), 2)
        self.assertLess(self.fractions[1][0], self.fractions[0][0])

    def test_the_backlog_is_reported_before_the_report_of_falling_behind(
            self):
        monitor = self.watching()
        events = []
        monitor.backlog.connect(lambda f: events.append('backlog'))
        monitor.behind.connect(lambda lag: events.append('behind'))
        self.capture(monitor, 12.)
        self.assertEqual(events, ['backlog', 'behind'])

    def test_the_limit_can_be_changed(self):
        monitor = self.watching(lagLimit=5.)
        self.capture(monitor, 12.)
        self.assertEqual(self.lags, [])

    def test_a_small_memory_budget_counts_as_falling_behind(self):
        # 0.5 s of a 30 Hz source of 16-byte frames
        monitor = self.watching(maxMemory=0.5 * 30 * _FRAME.nbytes)
        self.capture(monitor, 10.6)
        self.assertEqual(len(self.lags), 1)

    def test_a_large_budget_leaves_the_time_limit_in_charge(self):
        monitor = self.watching(maxMemory=1e12)
        self.capture(monitor, 10.9)
        self.assertEqual(self.lags, [])
        self.capture(monitor, 12.)
        self.assertEqual(len(self.lags), 1)

    def test_the_budget_defaults_to_most_of_the_available_memory(self):
        free = SimpleNamespace(available=1000)
        with patch('psutil.virtual_memory', return_value=free):
            monitor = self.watching()
        self.assertEqual(monitor._budget, 800)

    def test_a_given_budget_overrides_the_default(self):
        self.assertEqual(self.watching(maxMemory=123)._budget, 123)

    def test_a_writer_that_has_seen_nothing_is_not_late(self):
        monitor = self.watching()
        self.writer.received = None
        self.capture(monitor, 99.)
        self.assertEqual(self.lags, [])

    def test_a_frame_without_information_is_ignored(self):
        monitor = self.watching()
        monitor.check(_FRAME)
        self.assertEqual((self.fractions, self.lags), ([], []))

    def test_a_frame_that_arrives_after_stopping_is_ignored(self):
        monitor = self.watching()
        monitor.stop()
        self.capture(monitor, 99.)
        self.assertEqual(self.lags, [])

    def test_starting_again_clears_the_backlog(self):
        monitor = self.watching()
        self.capture(monitor, 12.)
        monitor.start(self.writer, 30.)
        self.capture(monitor, 12.)
        self.assertEqual(len(self.lags), 2)


if __name__ == '__main__':
    unittest.main()
