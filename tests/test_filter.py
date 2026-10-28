'''Tests for the Filter factory.'''
import unittest
from qtpy import QtWidgets
import numpy as np
import QVideo
from QVideo.lib import Filter
from QVideo.lib.QVideoFilter import VideoFilter
from QVideo.lib._camera import _CameraProxy

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestListing(unittest.TestCase):

    def test_no_arguments_list_the_names_sorted(self):
        names = Filter()
        self.assertEqual(names, sorted(names))
        self.assertGreater(len(names), 10)
        self.assertTrue(all(isinstance(name, str) for name in names))

    def test_the_names_include_known_filters(self):
        self.assertIn('Canny', Filter())
        self.assertIn('Dark Frame', Filter())

    def test_the_package_exports_it(self):
        self.assertIs(QVideo.Filter, Filter)


class TestBuilding(unittest.TestCase):

    def test_a_name_gives_a_list_with_one_filter(self):
        filters = Filter('Canny')
        self.assertEqual(len(filters), 1)
        self.assertIsInstance(filters[0], VideoFilter)

    def test_names_as_arguments_keep_their_order(self):
        filters = Filter('Invert', 'Canny')
        self.assertEqual([type(f).__name__ for f in filters],
                         ['InvertFilter', 'EdgeFilter'])

    def test_a_list_of_names_is_the_same_as_arguments(self):
        listed = Filter(['Invert', 'Canny'])
        self.assertEqual([type(f) for f in listed],
                         [type(f) for f in Filter('Invert', 'Canny')])

    def test_case_and_spaces_do_not_matter(self):
        for name in ('dark frame', 'DarkFrame', 'Dark  Frame', 'darkframe'):
            with self.subTest(name):
                self.assertEqual(type(Filter(name)[0]).__name__,
                                 'DarkFrameFilter')

    def test_every_listed_name_builds_a_filter_that_runs(self):
        frame = np.full((32, 48), 100, np.uint8)
        for name in Filter():
            with self.subTest(name):
                video_filter, = Filter(name)
                self.assertIsInstance(video_filter, VideoFilter)
                video_filter(frame.copy())

    def test_each_call_builds_new_filters(self):
        self.assertIsNot(Filter('Invert')[0], Filter('Invert')[0])

    def test_the_filters_are_ready_to_use_without_a_widget(self):
        invert, = Filter('Invert')
        frame = np.full((4, 4), 10, np.uint8)
        self.assertTrue((invert(frame) == 245).all())


class TestErrors(unittest.TestCase):

    def test_an_unknown_name_raises_value_error(self):
        with self.assertRaises(ValueError) as caught:
            Filter('zzzz')
        self.assertIn("'zzzz'", str(caught.exception))
        self.assertIn('Filter() lists', str(caught.exception))

    def test_a_near_miss_suggests_the_name(self):
        with self.assertRaises(ValueError) as caught:
            Filter('cany')
        self.assertIn("Did you mean 'Canny'?", str(caught.exception))

    def test_nothing_is_built_when_one_name_is_wrong(self):
        with self.assertRaises(ValueError):
            Filter('Invert', 'nonesuch')


class TestWithCamera(unittest.TestCase):

    def test_filters_assign_to_a_camera(self):
        proxy = _CameraProxy([('noise', 0)])
        proxy.filters = Filter('Invert')
        self.assertEqual(len(proxy.filters), 1)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
