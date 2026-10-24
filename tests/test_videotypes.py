'''Unit tests for QVideo.lib.videotypes.'''
import dataclasses
import time
import unittest
from QVideo.lib.videotypes import FrameInfo


class TestFrameInfo(unittest.TestCase):

    def test_fields(self):
        info = FrameInfo(index=3, timestamp=1.5, hardware_timestamp=2.5)
        self.assertEqual(info.index, 3)
        self.assertEqual(info.timestamp, 1.5)
        self.assertEqual(info.hardware_timestamp, 2.5)

    def test_hardware_timestamp_defaults_to_none(self):
        self.assertIsNone(FrameInfo(0, 0.).hardware_timestamp)

    def test_is_immutable(self):
        info = FrameInfo(0, 0.)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            info.index = 1

    def test_uses_slots(self):
        self.assertFalse(hasattr(FrameInfo(0, 0.), '__dict__'))

    def test_equality_and_hash(self):
        self.assertEqual(FrameInfo(1, 2.), FrameInfo(1, 2.))
        self.assertEqual(hash(FrameInfo(1, 2.)), hash(FrameInfo(1, 2.)))

    def test_wallclock_matches_time_for_current_timestamp(self):
        info = FrameInfo(0, time.perf_counter())
        self.assertAlmostEqual(info.wallclock, time.time(), delta=0.05)

    def test_wallclock_differences_follow_timestamps(self):
        a = FrameInfo(0, 100.)
        b = FrameInfo(1, 100.25)
        self.assertAlmostEqual(b.wallclock - a.wallclock, 0.25, places=3)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
