'''Unit tests for QVideo.lib.imageops.'''
import os
import tempfile
import unittest
import numpy as np
from qtpy import QtGui, QtWidgets
from QVideo.lib.imageops import (grayscale, to8bit, stretch16,
                                 save_image)

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


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


class TestSaveImage(unittest.TestCase):

    def path(self, suffix='.png'):
        f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def roundtrip(self, image, suffix='.png', levels=None):
        path = self.path(suffix)
        save_image(image, path, levels)
        return QtGui.QImage(path)

    def test_gray_pixels_read_back_equal(self):
        image = np.arange(24, dtype=np.uint8).reshape(4, 6) * 10
        loaded = self.roundtrip(image)
        self.assertEqual((loaded.height(), loaded.width()), (4, 6))
        for y in range(4):
            for x in range(6):
                self.assertEqual(loaded.pixelColor(x, y).red(), image[y, x])

    def test_rgb_pixels_read_back_equal(self):
        image = np.zeros((3, 5, 3), dtype=np.uint8)
        image[1, 2] = (10, 20, 30)
        color = self.roundtrip(image).pixelColor(2, 1)
        self.assertEqual((color.red(), color.green(), color.blue()),
                         (10, 20, 30))

    def test_rgba_pixels_read_back_equal(self):
        image = np.zeros((3, 5, 4), dtype=np.uint8)
        image[1, 2] = (10, 20, 30, 128)
        color = self.roundtrip(image).pixelColor(2, 1)
        self.assertEqual((color.red(), color.green(), color.blue(),
                          color.alpha()), (10, 20, 30, 128))

    def test_an_image_that_is_not_contiguous_is_saved(self):
        image = np.arange(48, dtype=np.uint8).reshape(6, 8)[::2, ::2]
        loaded = self.roundtrip(image)
        self.assertEqual(loaded.pixelColor(1, 1).red(), image[1, 1])

    def test_gray_16_bit_keeps_16_bits_stretched_to_the_levels(self):
        image = np.zeros((4, 6), dtype=np.uint16)
        image[:, 3:] = 4095
        loaded = self.roundtrip(image, levels=(0., 4095.))
        self.assertEqual(loaded.depth(), 16)
        self.assertEqual(loaded.pixelColor(5, 0).red(), 255)
        self.assertEqual(loaded.pixelColor(0, 0).red(), 0)

    def test_tiff_holds_16_bits(self):
        image = np.full((4, 6), 2048, dtype=np.uint16)
        loaded = self.roundtrip(image, '.tiff', (0., 4095.))
        self.assertEqual(loaded.depth(), 16)

    def test_jpeg_gets_8_bits(self):
        image = np.full((4, 6), 4095, dtype=np.uint16)
        loaded = self.roundtrip(image, '.jpg', (0., 4095.))
        self.assertEqual(loaded.pixelColor(0, 0).red(), 255)

    def test_color_16_bit_gets_8_bits(self):
        image = np.full((4, 6, 3), 4095, dtype=np.uint16)
        loaded = self.roundtrip(image, levels=(0., 4095.))
        self.assertEqual(loaded.pixelColor(0, 0).red(), 255)

    def test_without_levels_the_whole_range_is_used(self):
        image = np.full((4, 6), 65535, dtype=np.uint16)
        self.assertEqual(self.roundtrip(image).pixelColor(0, 0).red(), 255)

    def test_a_dtype_that_cannot_be_saved_raises(self):
        with self.assertRaises(ValueError):
            save_image(np.zeros((4, 6), np.float32), self.path())

    def test_a_shape_that_cannot_be_saved_raises(self):
        with self.assertRaises(ValueError):
            save_image(np.zeros((4, 6, 2), np.uint8), self.path())

    def test_a_path_that_cannot_be_written_raises(self):
        with self.assertRaises(OSError):
            save_image(np.zeros((4, 6), np.uint8),
                       '/nonexistent-folder/image.png')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
