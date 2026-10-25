'''Unit tests for QVideo.lib.imageops.'''
import unittest
import numpy as np
from QVideo.lib.imageops import grayscale


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


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
