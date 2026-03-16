'''Unit tests for QFPSMeter.'''
import unittest
from unittest.mock import patch
from collections import deque
from pyqtgraph.Qt import QtTest, QtWidgets
from QVideo.lib.QFPSMeter import QFPSMeter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_meter(window=10):
    return QFPSMeter(window=window)


def ticked_meter(n, window=10):
    '''Return a meter that has received n ticks with uniform 10 ms spacing.'''
    meter = make_meter(window=window)
    times = iter(i * 0.01 for i in range(n + 1))
    with patch('time.perf_counter', side_effect=lambda: next(times)):
        for _ in range(n):
            meter.tick()
    return meter


class TestInit(unittest.TestCase):

    def test_creates_successfully(self):
        self.assertIsInstance(make_meter(), QFPSMeter)

    def test_default_window(self):
        self.assertEqual(make_meter().window, 10)

    def test_custom_window(self):
        self.assertEqual(make_meter(window=5).window, 5)

    def test_window_clamped_to_two_for_one(self):
        self.assertEqual(make_meter(window=1).window, 2)

    def test_window_clamped_to_two_for_zero(self):
        self.assertEqual(make_meter(window=0).window, 2)

    def test_window_clamped_to_two_for_negative(self):
        self.assertEqual(make_meter(window=-3).window, 2)

    def test_initial_value_is_zero(self):
        self.assertEqual(make_meter().value, 0.)

    def test_initial_buffer_is_empty(self):
        self.assertEqual(len(make_meter()._timestamps), 0)

    def test_buffer_maxlen_equals_window(self):
        meter = make_meter(window=7)
        self.assertEqual(meter._timestamps.maxlen, 7)


class TestTick(unittest.TestCase):

    def test_tick_appends_timestamp(self):
        meter = make_meter()
        meter.tick()
        self.assertEqual(len(meter._timestamps), 1)

    def test_ticks_below_window_do_not_emit(self):
        meter = make_meter(window=5)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        for _ in range(4):
            meter.tick()
        self.assertEqual(len(spy), 0)

    def test_value_zero_before_buffer_fills(self):
        meter = make_meter(window=5)
        for _ in range(4):
            meter.tick()
        self.assertEqual(meter.value, 0.)

    def test_emits_on_window_th_tick(self):
        meter = make_meter(window=5)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        for _ in range(5):
            meter.tick()
        self.assertEqual(len(spy), 1)

    def test_emits_on_every_tick_after_buffer_fills(self):
        meter = make_meter(window=5)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        for _ in range(10):
            meter.tick()
        self.assertEqual(len(spy), 6)   # ticks 5..10

    def test_emitted_fps_is_positive(self):
        meter = make_meter(window=5)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        for _ in range(5):
            meter.tick()
        self.assertGreater(spy[0][0], 0.)

    def test_emitted_fps_is_float(self):
        meter = make_meter(window=5)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        for _ in range(5):
            meter.tick()
        self.assertIsInstance(spy[0][0], float)

    def test_fps_calculation_accuracy(self):
        '''10 frames at 10 ms each → 100 fps.'''
        meter = make_meter(window=10)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        times = iter(i * 0.01 for i in range(11))
        with patch('time.perf_counter', side_effect=lambda: next(times)):
            for _ in range(10):
                meter.tick()
        self.assertAlmostEqual(spy[0][0], 100., places=5)

    def test_buffer_does_not_exceed_window(self):
        meter = make_meter(window=5)
        for _ in range(20):
            meter.tick()
        self.assertEqual(len(meter._timestamps), 5)

    def test_sliding_window_updates_estimate(self):
        '''Rate doubles halfway through; later emissions should reflect it.'''
        meter = make_meter(window=4)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        # first 4 ticks: 10 ms apart → 100 fps window
        slow = [i * 0.01 for i in range(4)]
        # next 4 ticks: 5 ms apart → 200 fps window
        fast = [slow[-1] + (i + 1) * 0.005 for i in range(4)]
        times = iter(slow + fast)
        with patch('time.perf_counter', side_effect=lambda: next(times)):
            for _ in range(8):
                meter.tick()
        first_fps = spy[0][0]
        last_fps = spy[-1][0]
        self.assertGreater(last_fps, first_fps)

    def test_zero_elapsed_does_not_update_value(self):
        meter = make_meter(window=3)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        times = iter([0.0, 0.0, 0.0])
        with patch('time.perf_counter', side_effect=lambda: next(times)):
            for _ in range(3):
                meter.tick()
        self.assertEqual(len(spy), 0)
        self.assertEqual(meter.value, 0.)

    def test_window_of_two_emits_on_second_tick(self):
        meter = make_meter(window=2)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        meter.tick()
        meter.tick()
        self.assertEqual(len(spy), 1)


class TestReset(unittest.TestCase):

    def test_reset_clears_value(self):
        meter = ticked_meter(10)
        meter.reset()
        self.assertEqual(meter.value, 0.)

    def test_reset_clears_buffer(self):
        meter = ticked_meter(10)
        meter.reset()
        self.assertEqual(len(meter._timestamps), 0)

    def test_reset_on_fresh_meter_does_not_raise(self):
        make_meter().reset()

    def test_reset_then_tick_does_not_emit_early(self):
        meter = make_meter(window=5)
        for _ in range(5):
            meter.tick()
        meter.reset()
        spy = QtTest.QSignalSpy(meter.fpsReady)
        for _ in range(4):
            meter.tick()
        self.assertEqual(len(spy), 0)

    def test_reset_then_fill_emits_again(self):
        meter = make_meter(window=5)
        for _ in range(5):
            meter.tick()
        meter.reset()
        spy = QtTest.QSignalSpy(meter.fpsReady)
        for _ in range(5):
            meter.tick()
        self.assertEqual(len(spy), 1)


class TestValue(unittest.TestCase):

    def test_value_zero_before_first_window(self):
        meter = make_meter(window=5)
        for _ in range(4):
            meter.tick()
        self.assertEqual(meter.value, 0.)

    def test_value_matches_last_emission(self):
        meter = make_meter(window=5)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        for _ in range(5):
            meter.tick()
        self.assertAlmostEqual(meter.value, spy[0][0])

    def test_value_updates_on_each_tick_after_fill(self):
        meter = make_meter(window=4)
        spy = QtTest.QSignalSpy(meter.fpsReady)
        times = iter(i * 0.01 for i in range(8))
        with patch('time.perf_counter', side_effect=lambda: next(times)):
            for _ in range(7):
                meter.tick()
        self.assertEqual(len(spy), 4)


if __name__ == '__main__':
    unittest.main()
