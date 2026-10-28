'''Unit tests for launch() and the applications that call it.'''
import runpy
import threading
import time
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

    def windows(self):
        '''Main windows on screen, but not those of earlier tests.'''
        return [w for w in app.topLevelWidgets()
                if isinstance(w, QtWidgets.QMainWindow) and w.isVisible()
                and w not in self.earlier]

    def run_launch(self, widget, **kwargs):
        '''Launch *widget*; return the mocked tree and the window.'''
        shown = []
        self.earlier = [w for w in app.topLevelWidgets()]

        def run():
            # Let the camera open on its thread and the window be built.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not self.windows():
                app.processEvents()
                time.sleep(0.005)
            shown.extend(self.windows())

        camera = MagicMock()
        with patch.object(launch_module, 'open_camera',
                          return_value=('noise', camera)), \
                patch.object(launch_module, 'make_tree') as make_tree, \
                patch.object(launch_module.pg, 'mkQApp') as make_app, \
                patch.object(launch_module.pg, 'exec', run), \
                patch.object(launch_module.QtWidgets, 'QShortcut'):
            launch(widget, 'Title', **kwargs)
        self.make_app = make_app
        self.camera = camera
        for window in shown:
            self.addCleanup(window.close)
        return make_tree, shown[0]

    def test_the_widget_is_built_from_the_started_camera(self):
        make_tree, window = self.run_launch(_Widget)
        make_tree.assert_called_once_with('noise', self.camera)
        tree = make_tree.return_value.start.return_value
        self.assertIs(window.centralWidget().tree, tree)

    def splashes(self):
        '''Splash screens on screen, but not those of earlier tests.'''
        return [w for w in app.topLevelWidgets()
                if isinstance(w, QtWidgets.QSplashScreen) and w.isVisible()
                and w not in self.earlier]

    def test_a_splash_screen_waits_for_the_camera(self):
        self.earlier = list(app.topLevelWidgets())
        gate = threading.Event()
        seen = {}

        def open_slowly():
            gate.wait(5)
            return 'noise', MagicMock()

        def run():
            splash, = self.splashes()
            seen['notice'] = splash.message()
            seen['windows'] = len(self.windows())
            gate.set()
            deadline = time.monotonic() + 5
            while not self.windows() and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.005)
            seen['splashes'] = len(self.splashes())
            self.addCleanup(self.windows()[0].close)

        with patch.object(launch_module, 'open_camera', open_slowly), \
                patch.object(launch_module, 'make_tree'), \
                patch.object(launch_module.pg, 'mkQApp'), \
                patch.object(launch_module.pg, 'exec', run), \
                patch.object(launch_module.QtWidgets, 'QShortcut'):
            launch(_Widget, 'Title')
        self.assertEqual(seen['notice'], 'Opening the camera...')
        self.assertEqual(seen['windows'], 0)  # nothing to show yet
        self.assertEqual(seen['splashes'], 0)  # gone once the window shows

    def test_a_camera_that_cannot_open_ends_the_program(self):
        with patch.object(launch_module, 'open_camera',
                          side_effect=RuntimeError('no camera')), \
                patch.object(launch_module.pg, 'mkQApp') as make_app, \
                patch.object(launch_module.QtWidgets, 'QShortcut'):
            quits = []
            make_app.return_value.quit = lambda: quits.append(1)
            make_app.return_value.aboutToQuit = MagicMock()

            def run():
                deadline = time.monotonic() + 5
                while not quits and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(0.005)
            with patch.object(launch_module.pg, 'exec', run):
                with self.assertRaises(SystemExit) as raised:
                    launch(_Widget, 'Title')
        self.assertIn('no camera', str(raised.exception))

    def test_the_camera_is_closed_if_the_window_is_gone_before_it_opens(self):
        camera = MagicMock()

        def open_slowly():
            time.sleep(0.2)
            return 'noise', camera

        with patch.object(launch_module, 'open_camera', open_slowly), \
                patch.object(launch_module.pg, 'mkQApp'), \
                patch.object(launch_module.QtWidgets, 'QShortcut'):
            quitting = []

            def run():
                quitting[0]()  # the application quits at once

            with patch.object(launch_module.pg, 'exec', run):
                with patch.object(launch_module.pg, 'mkQApp') as make_app:
                    make_app.return_value.aboutToQuit.connect = \
                        quitting.append
                    launch(_Widget, 'Title')
        camera.close.assert_called_once()

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
