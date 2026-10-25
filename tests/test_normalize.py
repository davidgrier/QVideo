'''Unit tests for Normalize and SmoothNormalize.'''
import unittest
import unittest.mock
import numpy as np
from QVideo.filters.normalize import Normalize, SmoothNormalize
from QVideo.filters.median import Median
from QVideo.filters.momedian import MoMedian


_SHAPE = (4, 4)
# Uniform frame: median and normalization are straightforward to predict
_FRAME = np.full(_SHAPE, 100, dtype=np.uint8)


def make_normalize(**kwargs) -> Normalize:
    return Normalize(**kwargs)


def make_smooth(**kwargs) -> SmoothNormalize:
    return SmoothNormalize(**kwargs)


class TestNormalize(unittest.TestCase):

    def test_get_before_add_raises(self):
        f = make_normalize()
        with self.assertRaises(RuntimeError):
            f.get()

    def test_inherits_median(self):
        f = make_normalize()
        self.assertIsInstance(f, Median)

    def test_default_scale(self):
        f = make_normalize()
        self.assertTrue(f.scale)

    def test_default_mean(self):
        f = make_normalize()
        self.assertAlmostEqual(f.mean, 100.)

    def test_default_darkcount(self):
        f = make_normalize()
        self.assertEqual(f.darkcount, 0)

    def test_custom_darkcount(self):
        f = make_normalize(darkcount=10)
        self.assertEqual(f.darkcount, 10)

    def test_add_does_not_mutate_input(self):
        f = make_normalize()
        original = _FRAME.copy()
        f.add(_FRAME)
        np.testing.assert_array_equal(_FRAME, original)

    def test_add_stores_fg(self):
        f = make_normalize()
        f.add(_FRAME)
        self.assertIsNotNone(f._fg)

    def test_fg_has_darkcount_subtracted(self):
        darkcount = 10
        f = make_normalize(darkcount=darkcount)
        f.add(_FRAME)
        expected = _FRAME - darkcount
        np.testing.assert_array_equal(f._fg, expected)

    def test_get_returns_uint8_when_scale_true(self):
        f = make_normalize(scale=True)
        for _ in range(3):
            f.add(_FRAME)
        result = f.get()
        self.assertEqual(result.dtype, np.uint8)

    def test_get_zero_where_background_is_zero(self):
        '''Division by zero background produces zero output, not garbage.'''
        f = make_normalize()
        zero_frame = np.zeros(_SHAPE, dtype=np.uint8)
        for _ in range(3):
            f.add(zero_frame)
        result = f.get()
        np.testing.assert_array_equal(result, np.zeros(_SHAPE, dtype=np.uint8))

    def test_normalized_uniform_frame_equals_mean(self):
        '''Uniform foreground over uniform background → output equals mean.'''
        f = make_normalize(scale=True, mean=100.)
        for _ in range(3):
            f.add(_FRAME)
        result = f.get()
        # All pixels should be mean (100) when fg == bg
        np.testing.assert_array_equal(result, np.full(_SHAPE, 100, dtype=np.uint8))


def reference_normalize(fg, bg, scale, mean):
    '''The original masked-divide implementation.'''
    result = np.zeros_like(fg, dtype=np.float32)
    np.divide(fg, bg, out=result, where=(bg != 0))
    if scale:
        result = mean * result
    return result.astype(np.uint8)


class TestNormalizeMatchesReference(unittest.TestCase):

    def frames(self):
        rng = np.random.default_rng(5)
        fg = rng.integers(0, 256, (24, 32, 3), dtype=np.uint8)
        bg = rng.integers(0, 256, (24, 32, 3), dtype=np.uint8)
        bg[::5] = 0                       # some zero background
        return fg, bg

    def test_matches_the_masked_divide_with_scaling(self):
        fg, bg = self.frames()
        f = make_normalize(scale=True, mean=100.)
        f._fg = fg
        with unittest.mock.patch.object(Median, 'get', return_value=bg):
            result = f.get()
        np.testing.assert_array_equal(
            result, reference_normalize(fg, bg, True, 100.))

    def test_matches_the_masked_divide_without_scaling(self):
        fg, bg = self.frames()
        f = make_normalize(scale=False)
        f._fg = fg
        with unittest.mock.patch.object(Median, 'get', return_value=bg):
            result = f.get()
        np.testing.assert_array_equal(
            result, reference_normalize(fg, bg, False, 1.))

    def test_zero_background_gives_zero_output(self):
        fg = np.full((4, 4), 50, dtype=np.uint8)
        bg = np.zeros((4, 4), dtype=np.uint8)
        f = make_normalize(scale=False)
        f._fg = fg
        with unittest.mock.patch.object(Median, 'get', return_value=bg):
            self.assertFalse(f.get().any())

    def test_fractional_background_is_not_clamped(self):
        fg = np.full((4, 4), 1, dtype=np.float32)
        bg = np.full((4, 4), 0.5, dtype=np.float32)
        f = make_normalize(scale=False)
        f._fg = fg
        with unittest.mock.patch.object(Median, 'get', return_value=bg):
            self.assertTrue((f.get() == 2).all())


class TestSmoothNormalize(unittest.TestCase):

    def test_inherits_momedian(self):
        f = make_smooth()
        self.assertIsInstance(f, MoMedian)

    def test_default_scale(self):
        f = make_smooth()
        self.assertTrue(f.scale)

    def test_default_mean(self):
        f = make_smooth()
        self.assertAlmostEqual(f.mean, 100.)

    def test_default_darkcount(self):
        f = make_smooth()
        self.assertEqual(f.darkcount, 0)

    def test_add_does_not_mutate_input(self):
        f = make_smooth()
        original = _FRAME.copy()
        f.add(_FRAME)
        np.testing.assert_array_equal(_FRAME, original)

    def test_get_returns_uint8_when_scale_true(self):
        f = make_smooth(scale=True)
        for _ in range(3):
            f.add(_FRAME)
        result = f.get()
        self.assertEqual(result.dtype, np.uint8)

    def test_get_zero_where_background_is_zero(self):
        f = make_smooth()
        zero_frame = np.zeros(_SHAPE, dtype=np.uint8)
        for _ in range(3):
            f.add(zero_frame)
        result = f.get()
        np.testing.assert_array_equal(result, np.zeros(_SHAPE, dtype=np.uint8))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
