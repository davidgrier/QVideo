'''Unit tests for launch() and the applications that call it.'''
import runpy
import unittest
import warnings
from unittest.mock import MagicMock, patch
from qtpy import QtWidgets
from QVideo.lib import QFilterRack
from QVideo.lib import launch
from QVideo.lib import _launch as launch_module


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestLaunch(unittest.TestCase):

    def run_launch(self, widget, **kwargs):
        with patch.object(launch_module, 'choose_camera') as choose, \
                patch.object(launch_module.pg, 'mkQApp') as make_app, \
                patch.object(launch_module.pg, 'exec') as run, \
                patch.object(launch_module.QtWidgets, 'QShortcut'):
            launch(widget, 'Title', **kwargs)
        return choose, make_app, run

    def test_the_window_is_built_from_the_started_camera(self):
        window = MagicMock()
        widget = MagicMock(return_value=window)
        choose, _, _ = self.run_launch(widget)
        widget.assert_called_once_with(choose.return_value.start.return_value)

    def test_further_arguments_reach_the_window(self):
        widget = MagicMock()
        self.run_launch(widget, filters=['Canny'])
        self.assertEqual(widget.call_args.kwargs, {'filters': ['Canny']})

    def test_the_application_is_named_and_the_window_shown_and_run(self):
        window = MagicMock()
        _, make_app, run = self.run_launch(MagicMock(return_value=window))
        make_app.assert_called_once_with('Title')
        window.show.assert_called_once()
        run.assert_called_once()

    def test_a_missing_package_ends_the_program_with_its_message(self):
        widget = MagicMock(side_effect=ImportError('install trackpy'))
        with self.assertRaises(SystemExit) as raised:
            self.run_launch(widget)
        self.assertIn('install trackpy', str(raised.exception))


APPLICATIONS = [('QVideo.demos.demo', 'Demo'),
                ('QVideo.demos.filterdemo', 'FilterDemo'),
                ('QVideo.demos.filterrackdemo', 'FilterRackDemo'),
                ('QVideo.demos.ROIdemo', 'ROIDemo'),
                ('QVideo.demos.histogramdemo', 'HistogramDemo'),
                ('QVideo.demos.uniformitydemo', 'UniformityDemo'),
                ('QVideo.demos.circulardemo', 'CircularDemo'),
                ('QVideo.demos.compositedemo', 'CompositeDemo'),
                ('QVideo.demos.trackpydemo', 'TrackpyDemo'),
                ('QVideo.demos.combineddemo', 'CombinedDemo'),
                ('QVideo.demos.yolodemo', 'YoloDemo')]


def run_as_script(name):
    '''Run module *name* as ``python -m`` would; return the launch mock.'''
    with patch('QVideo.lib.launch') as mock_launch, \
            warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        runpy.run_module(name, run_name='__main__')
    return mock_launch


class TestMain(unittest.TestCase):

    def test_every_demo_launches_its_own_class(self):
        for name, cls in APPLICATIONS:
            with self.subTest(application=cls):
                mock_launch = run_as_script(name)
                mock_launch.assert_called_once()
                self.assertEqual(mock_launch.call_args.args[0].__name__,
                                 cls)

    def test_the_camcorder_launches_itself(self):
        from QVideo import QCamcorder
        with patch.object(QCamcorder, 'launch') as mock_launch:
            QCamcorder.main()
        mock_launch.assert_called_once()
        self.assertIs(mock_launch.call_args.args[0], QCamcorder.QCamcorder)

    def test_the_filter_demo_asks_for_filters_that_exist(self):
        mock_launch = run_as_script('QVideo.demos.filterdemo')
        available = QFilterRack.availableFilters()
        for name in mock_launch.call_args.kwargs['filters']:
            self.assertIn(name, available)


if __name__ == '__main__':
    unittest.main()
