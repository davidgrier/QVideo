'''Unit tests for launch() and the applications that call it.'''
import runpy
import unittest
import warnings
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
from QVideo.lib import QFilterRack
from QVideo.lib import launch
from QVideo.lib import _launch as launch_module


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Widget(QtWidgets.QWidget):
    '''Stands in for an application: it records how it was built.'''

    def __init__(self, tree, **kwargs):
        super().__init__()
        self.tree = tree
        self.kwargs = kwargs


class _Talker(_Widget):
    message = QtCore.Signal(str)


class TestLaunch(unittest.TestCase):

    def run_launch(self, widget, **kwargs):
        '''Launch *widget*; return the camera chooser and the window.'''
        shown = []

        def run():
            shown.extend(w for w in app.topLevelWidgets()
                         if isinstance(w, QtWidgets.QMainWindow)
                         and w.isVisible())

        with patch.object(launch_module, 'choose_camera') as choose, \
                patch.object(launch_module.pg, 'mkQApp') as make_app, \
                patch.object(launch_module.pg, 'exec', run), \
                patch.object(launch_module.QtWidgets, 'QShortcut'):
            launch(widget, 'Title', **kwargs)
        self.make_app = make_app
        for window in shown:
            self.addCleanup(window.close)
        return choose, shown[0]

    def test_the_widget_is_built_from_the_started_camera(self):
        choose, window = self.run_launch(_Widget)
        tree = choose.return_value.start.return_value
        self.assertIs(window.centralWidget().tree, tree)

    def test_further_arguments_reach_the_widget(self):
        _, window = self.run_launch(_Widget, filters=['Canny'])
        self.assertEqual(window.centralWidget().kwargs,
                         {'filters': ['Canny']})

    def test_the_widget_is_the_center_of_a_main_window(self):
        _, window = self.run_launch(_Widget)
        self.assertIsInstance(window, QtWidgets.QMainWindow)
        self.assertIsInstance(window.centralWidget(), _Widget)

    def test_the_application_and_the_window_are_titled(self):
        _, window = self.run_launch(_Widget)
        self.make_app.assert_called_once_with('Title')
        self.assertEqual(window.windowTitle(), 'Title')

    def test_messages_appear_in_the_status_bar(self):
        _, window = self.run_launch(_Talker)
        window.centralWidget().message.emit('falling behind')
        self.assertEqual(window.statusBar().currentMessage(),
                         'falling behind')

    def test_a_widget_without_messages_is_left_alone(self):
        _, window = self.run_launch(_Widget)
        self.assertIsNone(window.findChild(QtWidgets.QStatusBar))

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
