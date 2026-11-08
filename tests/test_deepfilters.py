'''Filters that keep the scale of a frame of more than 8 bits.'''
import unittest
import numpy as np
from qtpy import QtWidgets
from QVideo.lib.QFilterPipeline import QFilterPipeline
from QVideo.lib.QVideoFilter import VideoFilter, prepare
from QVideo.lib.QFilterRack import QFilterRack
from QVideo.filters import QInvertFilter, QThresholdFilter
from QVideo.interactive import camera as camera_module
from QVideo.filters import (DarkFrameFilter, FlatFieldFilter, InvertFilter,
                            SmoothingFilter, UnsharpFilter, DoGFilter,
                            ThresholdFilter, MoMean, Median, MoMedian,
                            Normalize, SampleHold, ROIFilter)

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

#: A camera of 12 bits: the counts go from 0 to 4095.
LEVELS = (0., 4095.)


def counts(value, shape=(16, 16)):
    '''A uint16 frame of 12 bit counts.'''
    return np.full(shape, value, dtype=np.uint16)


def ramp(shape=(16, 16)):
    '''A uint16 frame that goes from 0 to 4095 across the rows.'''
    row = np.linspace(0, 4095, shape[1]).astype(np.uint16)
    return np.tile(row, (shape[0], 1))


class TestPipelineGivesLevels(unittest.TestCase):

    '''The pipeline tells a deep filter the scale of the frame.'''

    def apply(self, video_filter, frame, levels):
        pipeline = QFilterPipeline(None, filters=[video_filter])
        self.addCleanup(pipeline.stop)
        return pipeline._apply(frame, levels)

    def test_a_deep_filter_is_given_the_levels(self):
        video_filter = InvertFilter()
        self.apply(video_filter, counts(10), LEVELS)
        self.assertEqual(video_filter.levels, LEVELS)

    def test_the_levels_are_none_for_an_8_bit_frame(self):
        video_filter = InvertFilter()
        video_filter.levels = LEVELS
        self.apply(video_filter, np.zeros((4, 4), np.uint8), None)
        self.assertIsNone(video_filter.levels)

    def test_a_deep_filter_gets_the_counts_and_the_levels_stay(self):
        frame, levels = self.apply(InvertFilter(), counts(1000), LEVELS)
        self.assertEqual(frame.dtype, np.uint16)
        self.assertEqual(levels, LEVELS)

    def test_a_filter_that_is_not_deep_gets_8_bits(self):
        class Plain(VideoFilter):
            pass
        frame, levels = self.apply(Plain(), counts(4095), LEVELS)
        self.assertEqual(frame.dtype, np.uint8)
        self.assertEqual(int(frame[0, 0]), 255)
        self.assertIsNone(levels)

    def test_bounds_without_levels_are_the_range_of_the_type(self):
        video_filter = VideoFilter()
        self.assertEqual(video_filter.bounds(counts(1)), (0., 65535.))
        self.assertEqual(
            video_filter.bounds(np.zeros(1, np.uint8)), (0., 255.))
        video_filter.levels = LEVELS
        self.assertEqual(video_filter.bounds(counts(1)), LEVELS)
        self.assertEqual(
            video_filter.bounds(np.zeros(1, np.uint8)), (0., 255.))


class TestDarkAndFlat(unittest.TestCase):

    def capture(self, video_filter, frame):
        video_filter.nFrames = 2
        video_filter.capture()
        video_filter(frame)
        video_filter(frame)

    def test_dark_frame_subtracts_counts(self):
        video_filter = DarkFrameFilter()
        video_filter.levels = LEVELS
        self.capture(video_filter, counts(100))
        result = video_filter(counts(1100))
        self.assertEqual(result.dtype, np.uint16)
        self.assertTrue((result == 1000).all())

    def test_dark_frame_clips_at_zero(self):
        video_filter = DarkFrameFilter()
        self.capture(video_filter, counts(500))
        self.assertTrue((video_filter(counts(100)) == 0).all())

    def test_a_dark_frame_of_8_bits_does_not_correct_deep_frames(self):
        video_filter = DarkFrameFilter()
        self.capture(video_filter, np.full((16, 16), 10, np.uint8))
        frame = counts(1100)
        self.assertIs(video_filter(frame), frame)

    def test_dark_frame_of_8_bits_is_as_before(self):
        video_filter = DarkFrameFilter()
        self.capture(video_filter, np.full((16, 16), 10, np.uint8))
        result = video_filter(np.full((16, 16), 30, np.uint8))
        self.assertEqual(result.dtype, np.uint8)
        self.assertTrue((result == 20).all())

    def test_flat_field_keeps_the_type_and_clips_at_white(self):
        video_filter = FlatFieldFilter()
        video_filter.levels = LEVELS
        flat = counts(1000)
        flat[:, :8] = 500
        self.capture(video_filter, flat)
        result = video_filter(counts(4000))
        self.assertEqual(result.dtype, np.uint16)
        self.assertEqual(int(result.max()), 4095)


class TestInvert(unittest.TestCase):

    def test_counts_are_inverted_between_the_levels(self):
        video_filter = InvertFilter()
        video_filter.levels = LEVELS
        result = video_filter(ramp())
        self.assertEqual(result.dtype, np.uint16)
        self.assertTrue(np.array_equal(result, 4095 - ramp()))

    def test_without_levels_the_whole_range_is_used(self):
        result = InvertFilter()(counts(100))
        self.assertEqual(int(result[0, 0]), 65435)

    def test_8_bits_as_before(self):
        frame = np.full((4, 4), 10, np.uint8)
        self.assertTrue((InvertFilter()(frame) == 245).all())


class TestSmoothing(unittest.TestCase):

    def test_gaussian_and_box_are_deep_and_median_is_not(self):
        video_filter = SmoothingFilter()
        for method, deep in (('gaussian', True), ('box', True),
                             ('median', False)):
            with self.subTest(method=method):
                video_filter.method = method
                self.assertEqual(video_filter.deep, deep)

    def test_a_smoothed_deep_frame_keeps_type_and_scale(self):
        video_filter = SmoothingFilter(method='gaussian')
        result = video_filter(counts(3000))
        self.assertEqual(result.dtype, np.uint16)
        self.assertEqual(int(result[8, 8]), 3000)


class TestUnsharp(unittest.TestCase):

    def test_the_result_stays_below_white(self):
        video_filter = UnsharpFilter(radius=1., amount=5.)
        video_filter.levels = LEVELS
        frame = counts(3000)
        frame[6:10, 6:10] = 4000
        result = video_filter(frame)
        self.assertEqual(result.dtype, np.uint16)
        self.assertLessEqual(int(result.max()), 4095)

    def test_a_flat_frame_is_unchanged(self):
        result = UnsharpFilter()(counts(2000))
        self.assertTrue((result == 2000).all())


class TestDoG(unittest.TestCase):

    def test_the_response_is_in_counts(self):
        video_filter = DoGFilter(low_sigma=1., high_sigma=3.)
        video_filter.levels = LEVELS
        frame = counts(0)
        frame[8, 8] = 4000
        result = video_filter(frame)
        self.assertEqual(result.dtype, np.uint16)
        self.assertGreater(int(result.max()), 255)
        self.assertLessEqual(int(result.max()), 4095)


class TestThreshold(unittest.TestCase):

    def test_only_the_global_method_is_deep(self):
        video_filter = ThresholdFilter()
        for method in ThresholdFilter.METHODS:
            with self.subTest(method=method):
                video_filter.method = method
                self.assertEqual(video_filter.deep, method == 'Global')

    def test_global_threshold_is_the_same_fraction_of_the_range(self):
        video_filter = ThresholdFilter(threshold=127)
        video_filter.levels = LEVELS
        frame = counts(0)
        frame[:, :8] = 2000        # below 127 / 255 of 4095 (2039)
        frame[:, 8:] = 2100        # above it
        result = video_filter(frame)
        self.assertEqual(result.dtype, np.uint16)
        self.assertTrue((result[:, :8] == 0).all())
        self.assertTrue((result[:, 8:] == 4095).all())

    def test_8_bits_as_before(self):
        frame = np.zeros((4, 4), np.uint8)
        frame[:, 2:] = 200
        result = ThresholdFilter(threshold=127)(frame)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(int(result.max()), 255)


class TestBackgrounds(unittest.TestCase):

    def test_momean_follows_deep_frames(self):
        video_filter = MoMean(alpha=1.)
        result = video_filter(counts(3000))
        self.assertEqual(result.dtype, np.uint16)
        self.assertEqual(int(result[0, 0]), 3000)

    def test_momean_starts_again_when_the_type_changes(self):
        video_filter = MoMean(alpha=0.5)
        video_filter(counts(3000))
        result = video_filter(np.full((16, 16), 10, np.uint8))
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(int(result[0, 0]), 10)

    def test_momean_8_bits_as_before(self):
        result = MoMean(alpha=1.)(np.full((4, 4), 77, np.uint8))
        self.assertEqual(result.dtype, np.uint8)

    def test_median_and_momedian_keep_the_type(self):
        for cls in (Median, MoMedian):
            with self.subTest(cls=cls.__name__):
                video_filter = cls()
                result = None
                for _ in range(4):
                    result = video_filter(counts(3000))
                self.assertEqual(result.dtype, np.uint16)
                self.assertEqual(int(result[0, 0]), 3000)

    def test_median_starts_again_when_the_type_changes(self):
        video_filter = Median()
        for _ in range(4):
            video_filter(counts(3000))
        result = video_filter(np.full((16, 16), 10, np.uint8))
        self.assertEqual(result.dtype, np.uint8)

    def test_normalize_scales_to_the_white_level(self):
        video_filter = Normalize(mean=100.)
        video_filter.levels = LEVELS
        result = None
        for _ in range(4):
            result = video_filter(counts(2000))
        self.assertEqual(result.dtype, np.uint16)
        # 100 of 255 of the range
        self.assertAlmostEqual(float(result[0, 0]), 100 * 4095 / 255, delta=2)

    def test_normalize_8_bits_as_before(self):
        video_filter = Normalize(mean=100.)
        result = None
        for _ in range(4):
            result = video_filter(np.full((4, 4), 50, np.uint8))
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(int(result[0, 0]), 100)

    def test_sample_hold_passes_the_counts_while_it_waits(self):
        video_filter = SampleHold()
        video_filter.levels = LEVELS
        result = video_filter(counts(2500))
        self.assertEqual(result.dtype, np.uint16)
        self.assertEqual(int(result[0, 0]), 2500)


class TestWhichAreDeep(unittest.TestCase):

    def test_the_filters_that_keep_the_scale(self):
        deep = (DarkFrameFilter, FlatFieldFilter, InvertFilter,
                UnsharpFilter, DoGFilter, MoMean, Median, MoMedian,
                Normalize, SampleHold, ROIFilter)
        for cls in deep:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(cls().deep)


class TestPrepare(unittest.TestCase):

    def test_a_callable_that_is_not_a_filter_gets_8_bits(self):
        frame, levels = prepare(lambda x: x, counts(4095), LEVELS)
        self.assertEqual(frame.dtype, np.uint8)
        self.assertIsNone(levels)

    def test_a_deep_filter_keeps_the_frame_and_gets_the_levels(self):
        video_filter = InvertFilter()
        original = counts(1)
        frame, levels = prepare(video_filter, original, LEVELS)
        self.assertIs(frame, original)
        self.assertEqual(levels, LEVELS)
        self.assertEqual(video_filter.levels, LEVELS)

    def test_8_bit_frames_pass_untouched(self):
        original = np.zeros((4, 4), np.uint8)
        frame, levels = prepare(InvertFilter(), original, None)
        self.assertIs(frame, original)
        self.assertIsNone(levels)


class TestRack(unittest.TestCase):

    def setUp(self):
        self.rack = QFilterRack(parent=None)
        self.addCleanup(self.rack.pipeline.stop)

    def switchOn(self, widget):
        widget.setChecked(True)
        self.rack.add(widget)
        return widget

    def test_deep_filters_in_a_rack_keep_the_counts(self):
        self.switchOn(QThresholdFilter())      # global, 127: deep
        self.switchOn(QInvertFilter())
        result = self.rack(counts(4095), LEVELS)
        self.assertEqual(result.dtype, np.uint16)
        self.assertEqual(int(result[0, 0]), 0)    # white, then inverted

    def test_a_filter_that_is_not_deep_gets_8_bits_from_a_rack(self):
        widget = self.switchOn(QThresholdFilter())
        widget.videoFilter.method = 'Otsu'
        frame = counts(0)
        frame[:, 8:] = 4095
        result = self.rack(frame, LEVELS)
        self.assertEqual(result.dtype, np.uint8)

    def test_without_levels_a_deep_frame_uses_the_whole_range(self):
        self.switchOn(QInvertFilter())
        result = self.rack(counts(100))
        self.assertEqual(int(result[0, 0]), 65435)

    def test_a_filter_that_is_off_does_not_scale(self):
        widget = self.switchOn(QInvertFilter())
        widget.setChecked(False)
        frame = counts(100)
        self.assertIs(self.rack(frame, LEVELS), frame)


class TestCameraProxy(unittest.TestCase):

    def test_filters_get_the_levels_of_the_camera(self):
        video_filter = InvertFilter()
        frame = camera_module._apply([video_filter], counts(100), LEVELS)
        self.assertEqual(int(frame[0, 0]), 3995)

    def test_a_filter_that_is_not_deep_gets_8_bits(self):
        seen = []
        camera_module._apply([lambda x: seen.append(x.dtype) or x],
                             counts(100), LEVELS)
        self.assertEqual(seen, [np.uint8])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
