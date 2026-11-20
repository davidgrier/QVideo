'''Tests for BayerFilter and QBayerFilter.'''
import unittest
import numpy as np
from qtpy.QtWidgets import QApplication
from QVideo.filters.bayer import BayerFilter, QBayerFilter

app = QApplication.instance() or QApplication([])

#: The colors of the pixels of the first two rows of each pattern.
LAYOUT = {'BayerRG': 'RGGB', 'BayerGR': 'GRBG',
          'BayerGB': 'GBRG', 'BayerBG': 'BGGR'}
CHANNEL = {'R': 0, 'G': 1, 'B': 2}


def mosaic(pattern, color, shape=(16, 20), dtype=np.uint8, value=200):
    '''Return the mosaic that a sensor of *pattern* sees of a scene of a
    single *color* ('R', 'G' or 'B'): a pixel has the value where its
    filter passes that color and zero elsewhere.'''
    image = np.zeros(shape, dtype=dtype)
    cells = LAYOUT[pattern]
    for index, filter_color in enumerate(cells):
        if filter_color == color:
            image[index // 2::2, index % 2::2] = value
    return image


class TestBayerFilter(unittest.TestCase):

    def setUp(self):
        self.f = BayerFilter()

    def test_the_default_is_off(self):
        self.assertEqual(self.f.pattern, 'Off')

    def test_get_none_when_no_data(self):
        self.f.pattern = 'BayerRG'
        self.assertIsNone(self.f.get())

    def test_an_unknown_pattern_is_rejected(self):
        with self.assertRaises(ValueError):
            self.f.pattern = 'BayerXX'
        with self.assertRaises(ValueError):
            BayerFilter(pattern='rggb')

    def test_off_passes_a_mosaic_through(self):
        frame = mosaic('BayerRG', 'R')
        self.assertIs(self.f(frame), frame)

    def test_a_mosaic_of_each_pattern_gives_the_color_that_it_saw(self):
        # Away from the edges, the scene has one color, whatever the
        # pattern: this fixes the names of OpenCV against those of GenICam.
        for pattern in LAYOUT:
            for color, channel in CHANNEL.items():
                with self.subTest(pattern=pattern, color=color):
                    self.f.pattern = pattern
                    result = self.f(mosaic(pattern, color))
                    self.assertEqual(result.shape, (16, 20, 3))
                    inner = result[2:-2, 2:-2]
                    want = np.zeros_like(inner)
                    want[..., channel] = 200
                    np.testing.assert_array_equal(inner, want)

    def test_a_deep_frame_keeps_its_depth_and_scale(self):
        self.f.pattern = 'BayerGR'
        frame = mosaic('BayerGR', 'B', dtype=np.uint16, value=3000)
        result = self.f(frame)
        self.assertEqual(result.dtype, np.uint16)
        np.testing.assert_array_equal(result[2:-2, 2:-2, 2], 3000)
        np.testing.assert_array_equal(result[2:-2, 2:-2, :2], 0)

    def test_the_filter_is_deep(self):
        self.assertTrue(self.f.deep)

    def test_color_frames_pass_through(self):
        self.f.pattern = 'BayerRG'
        for channels in (3, 4):
            with self.subTest(channels=channels):
                frame = np.full((8, 8, channels), 90, dtype=np.uint8)
                self.assertIs(self.f(frame), frame)

    def test_the_filter_does_not_change_its_input(self):
        self.f.pattern = 'BayerBG'
        frame = mosaic('BayerBG', 'G')
        before = frame.copy()
        self.f(frame)
        np.testing.assert_array_equal(frame, before)


class TestQBayerFilter(unittest.TestCase):

    def setUp(self):
        self.w = QBayerFilter()

    def test_filter_instance(self):
        self.assertIsInstance(self.w.videoFilter, BayerFilter)

    def test_title(self):
        self.assertEqual(self.w.title(), 'Bayer to RGB')

    def test_the_box_lists_off_and_the_four_patterns(self):
        box = self.w._patternBox
        items = [box.itemText(i) for i in range(box.count())]
        self.assertEqual(items, list(BayerFilter.PATTERNS))
        self.assertEqual(box.currentText(), 'Off')

    def test_choosing_a_pattern_sets_the_filter(self):
        self.w._patternBox.setCurrentText('BayerGB')
        self.assertEqual(self.w.videoFilter.pattern, 'BayerGB')

    def test_unchecked_passes_the_mosaic_through(self):
        self.w._patternBox.setCurrentText('BayerRG')
        frame = mosaic('BayerRG', 'R')
        self.assertIs(self.w(frame), frame)

    def test_checked_demosaics(self):
        self.w._patternBox.setCurrentText('BayerRG')
        self.w.setChecked(True)
        result = self.w(mosaic('BayerRG', 'R'))
        self.assertEqual(result.shape, (16, 20, 3))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
