'''Unit tests for the DNN helper.'''
import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np

from QVideo.lib.dnn import DNN, letterbox, prepare
from QVideo.tests.onnxfile import writeIdentity


class TestPrepare(unittest.TestCase):

    def test_gray_becomes_three_equal_channels(self):
        gray = np.arange(12, dtype=np.uint8).reshape(3, 4)
        out = prepare(gray)
        self.assertEqual(out.shape, (3, 4, 3))
        for channel in range(3):
            np.testing.assert_array_equal(out[..., channel], gray)

    def test_alpha_is_dropped(self):
        self.assertEqual(prepare(np.zeros((3, 4, 4), np.uint8)).shape,
                         (3, 4, 3))

    def test_uint16_is_scaled_to_eight_bits(self):
        out = prepare(np.full((2, 2), 65535, np.uint16))
        self.assertEqual(out.dtype, np.uint8)
        self.assertTrue((out == 255).all())

    def test_color_uint8_is_returned_as_is(self):
        image = np.zeros((3, 4, 3), np.uint8)
        self.assertIs(prepare(image), image)


class TestLetterbox(unittest.TestCase):

    def test_result_has_the_requested_size(self):
        out, _, _ = letterbox(np.zeros((100, 200, 3), np.uint8), (64, 64))
        self.assertEqual(out.shape, (64, 64, 3))

    def test_scale_and_pad_of_a_wide_image(self):
        _, scale, pad = letterbox(np.zeros((100, 200, 3), np.uint8),
                                  (64, 64))
        self.assertAlmostEqual(scale, 0.32)
        self.assertEqual(pad, (0., 16.))

    def test_the_margins_have_the_fill_color(self):
        out, _, _ = letterbox(np.zeros((100, 200, 3), np.uint8), (64, 64),
                              color=114)
        self.assertTrue((out[0] == 114).all())
        self.assertTrue((out[32] == 0).all())

    def test_a_point_maps_back_to_the_image(self):
        image = np.zeros((100, 200, 3), np.uint8)
        _, scale, (dx, dy) = letterbox(image, (64, 64))
        x, y = 100 * scale + dx, 50 * scale + dy      # the center
        self.assertAlmostEqual((x - dx) / scale, 100)
        self.assertAlmostEqual((y - dy) / scale, 50)

    def test_an_image_of_the_size_is_not_resized(self):
        image = np.full((32, 32, 3), 7, np.uint8)
        out, scale, pad = letterbox(image, (32, 32))
        np.testing.assert_array_equal(out, image)
        self.assertEqual((scale, pad), (1., (0., 0.)))


class TestDNN(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.path = writeIdentity(Path(cls.dir.name) / 'identity.onnx',
                                 (1, 3, 32, 48))

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_forward_returns_a_list_of_arrays(self):
        net = DNN(self.path, size=(48, 32))
        out = net.forward(np.zeros((32, 48, 3), np.uint8))
        self.assertIsInstance(out, list)
        self.assertEqual(out[0].shape, (1, 3, 32, 48))

    def test_pixels_are_scaled(self):
        net = DNN(self.path, size=(48, 32))
        image = np.random.default_rng(0).integers(
            0, 255, (32, 48, 3), dtype=np.uint8)
        out = net.forward(image)[0]
        np.testing.assert_allclose(out[0, 1], image[..., 1] / 255.,
                                   atol=1e-6)

    def test_swapRB_swaps_red_and_blue(self):
        image = np.zeros((32, 48, 3), np.uint8)
        image[..., 0] = 255
        out = DNN(self.path, size=(48, 32), swapRB=True).forward(image)[0]
        self.assertAlmostEqual(float(out[0, 2].mean()), 1.)
        self.assertAlmostEqual(float(out[0, 0].mean()), 0.)

    def test_mean_is_subtracted(self):
        image = np.full((32, 48, 3), 100, np.uint8)
        out = DNN(self.path, size=(48, 32), scale=1., mean=100.).forward(
            image)[0]
        self.assertAlmostEqual(float(abs(out).max()), 0.)

    def test_a_frame_is_resized_to_the_size_of_the_network(self):
        net = DNN(self.path, size=(48, 32))
        out = net.forward(np.zeros((64, 96, 3), np.uint8))[0]
        self.assertEqual(out.shape, (1, 3, 32, 48))

    def test_a_gray_frame_is_accepted(self):
        net = DNN(self.path, size=(48, 32))
        self.assertEqual(net.forward(np.zeros((32, 48), np.uint8))[0].shape,
                         (1, 3, 32, 48))

    def test_a_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            DNN(Path(self.dir.name) / 'nothing.onnx')

    def test_a_file_that_is_not_a_network_raises(self):
        bad = Path(self.dir.name) / 'bad.onnx'
        bad.write_bytes(b'not a network')
        with self.assertRaises(RuntimeError):
            DNN(bad)

    def test_the_engine_can_be_chosen(self):
        net = DNN(self.path, size=(48, 32), engine=cv2.dnn.ENGINE_CLASSIC)
        self.assertEqual(net.forward(np.zeros((32, 48, 3), np.uint8))[0]
                         .shape, (1, 3, 32, 48))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
