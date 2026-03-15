'''Unit tests for MoMedian.'''
import unittest
import numpy as np
from QVideo.filters.MoMedian import MoMedian


_SHAPE = (4, 4)
_A = np.full(_SHAPE, 10, dtype=np.uint8)
_B = np.full(_SHAPE, 20, dtype=np.uint8)
_C = np.full(_SHAPE, 30, dtype=np.uint8)


def make_filter(**kwargs) -> MoMedian:
    return MoMedian(**kwargs)


class TestMoMedian(unittest.TestCase):

    def test_default_order(self):
        f = make_filter()
        self.assertEqual(f.order, 1)

    def test_custom_order(self):
        f = make_filter(order=2)
        self.assertEqual(f.order, 2)

    def test_get_returns_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.get())

    def test_shape_none_before_add(self):
        f = make_filter()
        self.assertIsNone(f.shape)

    def test_shape_set_after_first_add(self):
        f = make_filter()
        f.add(_A)
        self.assertEqual(f.shape, _SHAPE)

    def test_get_returns_result_after_add(self):
        f = make_filter()
        f.add(_A)
        self.assertIsNotNone(f.get())

    def test_result_updated_every_frame(self):
        '''MoMedian produces a new result on every frame (unlike Median).'''
        f = make_filter()
        f.add(_A)
        r1 = f.get().copy()
        f.add(_B)
        r2 = f.get().copy()
        # After two distinct frames the estimate should change
        self.assertFalse(np.array_equal(r1, r2))

    def test_median_of_three_picks_middle_value(self):
        f = make_filter()
        f.add(_A)   # 10
        f.add(_B)   # 20
        f.add(_C)   # 30 → median is 20
        result = f.get()
        np.testing.assert_array_equal(result, _B)

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

    def test_reset_zeros_buffers(self):
        f = make_filter(data=_A)
        f.add(_A)
        f.reset()
        np.testing.assert_array_equal(f._result, np.zeros(_SHAPE, dtype=np.uint8))
        np.testing.assert_array_equal(f._buffer, np.zeros((2, *_SHAPE), dtype=np.uint8))

    def test_clear_forgets_shape(self):
        f = make_filter(data=_A)
        f._clear()
        self.assertIsNone(f.shape)

    def test_clear_sets_result_to_none(self):
        f = make_filter(data=_A)
        f._clear()
        self.assertIsNone(f._result)

    def test_order_setter_clears_state(self):
        f = make_filter(order=1, data=_A)
        f.order = 2
        self.assertIsNone(f.shape)
        self.assertIsNone(f._result)

    def test_reset_clears_index(self):
        f = make_filter(data=_A)
        f.add(_A)
        f.reset()
        self.assertEqual(f._index, 0)

    def test_does_not_mutate_input(self):
        f = make_filter()
        original = _A.copy()
        f.add(_A)
        np.testing.assert_array_equal(_A, original)


if __name__ == '__main__':
    unittest.main()
