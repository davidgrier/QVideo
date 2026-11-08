'''Unit tests for QVideo.lib.imageops.'''
import unittest
import numpy as np
from QVideo.lib.imageops import grayscale, to8bit, stretch16


class TestGrayscale(unittest.TestCase):

    def test_gray_frame_is_returned_unchanged(self):
        gray = np.arange(12, dtype=np.uint8).reshape(3, 4)
        self.assertIs(grayscale(gray), gray)

    def test_color_frame_becomes_a_2d_uint8_frame(self):
        color = np.zeros((5, 7, 3), dtype=np.uint8)
        gray = grayscale(color)
        self.assertEqual(gray.shape, (5, 7))
        self.assertEqual(gray.dtype, np.uint8)

    def test_four_channel_frame_is_accepted(self):
        self.assertEqual(grayscale(np.zeros((5, 7, 4), np.uint8)).shape,
                         (5, 7))

    def test_frames_are_rgb_ordered(self):
        pixel = lambda r, g, b: np.array([[[r, g, b]]], dtype=np.uint8)
        red, green, blue = (int(grayscale(pixel(*c))[0, 0])
                            for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255)))
        self.assertAlmostEqual(red, 0.299 * 255, delta=1)
        self.assertAlmostEqual(green, 0.587 * 255, delta=1)
        self.assertAlmostEqual(blue, 0.114 * 255, delta=1)

    def test_luminance_weights(self):
        rng = np.random.default_rng(0)
        color = rng.integers(0, 256, (20, 30, 3), dtype=np.uint8)
        expected = color @ np.array([0.299, 0.587, 0.114])
        diff = np.abs(grayscale(color).astype(float) - expected)
        self.assertLessEqual(diff.max(), 1.0)

    def test_monochrome_replicated_into_three_channels_is_preserved(self):
        rng = np.random.default_rng(1)
        gray = rng.integers(0, 256, (20, 30), dtype=np.uint8)
        np.testing.assert_array_equal(grayscale(np.dstack([gray] * 3)), gray)


class TestTo8bit(unittest.TestCase):

    def test_the_whole_range_of_uint16_by_default(self):
        frame = np.array([[0, 257, 65535]], np.uint16)
        np.testing.assert_array_equal(to8bit(frame), [[0, 1, 255]])

    def test_the_levels_become_black_and_white(self):
        frame = np.array([[0, 2048, 4095]], np.uint16)
        np.testing.assert_array_equal(to8bit(frame, (0, 4095)),
                                      [[0, 128, 255]])

    def test_values_outside_the_levels_saturate(self):
        frame = np.array([[100, 1000, 5000]], np.uint16)
        np.testing.assert_array_equal(to8bit(frame, (500, 1500)),
                                      [[0, 128, 255]])

    def test_the_type_is_uint8_and_the_shape_is_kept(self):
        for shape in ((6, 8), (6, 8, 3)):
            out = to8bit(np.zeros(shape, np.uint16), (0, 4095))
            self.assertEqual((out.dtype, out.shape), (np.uint8, shape))


class TestStretch16(unittest.TestCase):

    def test_the_levels_become_the_ends_of_the_range(self):
        frame = np.array([[0, 2047, 4095]], dtype=np.uint16)
        np.testing.assert_allclose(stretch16(frame, (0, 4095)),
                                   [[0, 32760, 65535]], atol=1)

    def test_values_outside_the_levels_saturate(self):
        frame = np.array([[100, 5000]], dtype=np.uint16)
        np.testing.assert_array_equal(stretch16(frame, (200, 4095)),
                                      [[0, 65535]])

    def test_the_default_leaves_the_frame_alone(self):
        frame = np.array([[0, 1, 65535]], dtype=np.uint16)
        self.assertIs(stretch16(frame), frame)

    def test_the_result_is_uint16_and_keeps_the_shape(self):
        frame = np.zeros((3, 4, 3), dtype=np.uint16)
        result = stretch16(frame, (0, 4095))
        self.assertEqual(result.dtype, np.uint16)
        self.assertEqual(result.shape, frame.shape)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
