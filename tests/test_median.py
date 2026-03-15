'''Unit tests for Median.'''
import unittest
import numpy as np
from QVideo.filters.Median import Median


_SHAPE = (4, 4)
_A = np.full(_SHAPE, 10, dtype=np.uint8)
_B = np.full(_SHAPE, 20, dtype=np.uint8)
_C = np.full(_SHAPE, 30, dtype=np.uint8)


def make_filter(**kwargs) -> Median:
    return Median(**kwargs)


class TestMedian(unittest.TestCase):

    def test_default_order(self):
        f = make_filter()
        self.assertEqual(f.order, 1)

    def test_custom_order(self):
        f = make_filter(order=2)
        self.assertEqual(f.order, 2)

    def test_data_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.get())

    def test_shape_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.shape)

    def test_not_ready_before_three_frames(self):
        f = make_filter()
        f.add(_A)
        f.add(_B)
        self.assertFalse(f.ready())

    def test_ready_after_three_frames(self):
        f = make_filter()
        f.add(_A)
        f.add(_B)
        f.add(_C)
        self.assertTrue(f.ready())

    def test_median_of_three_constant_frames(self):
        f = make_filter()
        frame = np.full(_SHAPE, 50, dtype=np.uint8)
        for _ in range(3):
            f.add(frame)
        result = f.get()
        np.testing.assert_array_equal(result, frame)

    def test_median_of_three_picks_middle_value(self):
        f = make_filter()
        f.add(_A)   # 10
        f.add(_B)   # 20
        f.add(_C)   # 30 → median is 20
        result = f.get()
        np.testing.assert_array_equal(result, _B)

    def test_get_resets_ready_flag(self):
        f = make_filter()
        for frame in (_A, _B, _C):
            f.add(frame)
        f.get()
        self.assertFalse(f.ready())

    def test_shape_set_after_first_add(self):
        f = make_filter()
        f.add(_A)
        self.assertEqual(f.shape, _SHAPE)

    def test_shape_change_reinitializes(self):
        f = make_filter()
        f.add(_A)
        new_frame = np.zeros((8, 8), dtype=np.uint8)
        f.add(new_frame)
        self.assertEqual(f.shape, (8, 8))

    def test_seed_data_sets_shape(self):
        f = make_filter(data=_A)
        self.assertEqual(f.shape, _SHAPE)

    def test_order_setter_reinitializes(self):
        f = make_filter(order=1)
        f.add(_A)
        f.order = 2
        self.assertIsNone(f.shape)

    def test_order_setter_same_value_is_noop(self):
        f = make_filter(order=1)
        f.add(_A)
        f.order = 1
        self.assertEqual(f.shape, _SHAPE)

    def test_reset_clears_ready(self):
        f = make_filter(data=_A)
        for frame in (_A, _B, _C):
            f.add(frame)
        f.reset()
        self.assertFalse(f.ready())

    def test_reset_clears_index(self):
        f = make_filter(data=_A)
        for frame in (_A, _B, _C):
            f.add(frame)
        f.reset()
        self.assertEqual(f._index, 0)

    def test_reset_zeros_buffers(self):
        f = make_filter(data=_A)
        f.reset()
        np.testing.assert_array_equal(f._result, np.zeros(_SHAPE, dtype=np.uint8))
        np.testing.assert_array_equal(f._buffer, np.zeros((2, *_SHAPE), dtype=np.uint8))

    def test_call_returns_result(self):
        f = make_filter()
        for frame in (_A, _B, _C):
            f(frame)
        result = f(_C)
        self.assertIsNotNone(result)

    def test_does_not_mutate_input(self):
        f = make_filter()
        original = _A.copy()
        f.add(_A)
        np.testing.assert_array_equal(_A, original)


if __name__ == '__main__':
    unittest.main()
