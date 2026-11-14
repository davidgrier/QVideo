'''Unit tests for launch() and the applications that call it.'''
import gc
import logging
import os
import runpy
import subprocess
import sys
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


def settle() -> None:
    '''Deliver what earlier tests left in the event queue, and delete what
    they dropped, before a test shows a window.

    A splash screen processes events when it is shown.  The suite crashed
    there twice (CI, Python 3.13 and 3.11 with PyQt6, 2026-11-13 and 14),
    in a callback that an earlier test had connected to a signal; the cause
    is not known, and a queue that is empty when the test starts cannot hand
    it a stale event.
    '''
    gc.collect()
    for _ in range(3):
        app.processEvents()
        QtCore.QCoreApplication.sendPostedEvents(
            None, QtCore.QEvent.Type.DeferredDelete)
    gc.collect()


def setUpModule() -> None:
    settle()


class _Widget(QtWidgets.QWidget):
    '''Stands in for an application: it records how it was built.'''

    def __init__(self, tree, **kwargs):
        super().__init__()
        self.tree = tree
        self.kwargs = kwargs


class _Talker(_Widget):
    message = QtCore.Signal(str)


class TestLaunch(unittest.TestCase):

    def setUp(self):
        settle()
        # launch() reads the command line, which here is that of pytest
        argv = patch.object(sys, 'argv', ['application'])
        argv.start()
        self.addCleanup(argv.stop)

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
        with patch.object(launch_module.chooser, 'open_camera',
                          return_value=('noise', camera)), \
                patch.object(launch_module.chooser, 'make_tree') as make_tree, \
                patch.object(launch_module.pg, 'mkQApp') as make_app, \
                patch.object(launch_module.pg, 'exec', run), \
                patch.object(launch_module.QtWidgets, 'QShortcut'):
            launch(widget, 'Title', **kwargs)
        self.make_app = make_app
        self.camera = camera
        for window in shown:
            self.addCleanup(window.close)
        return make_tree, shown[0]

    def launch_on(self, platform):
        '''Launch on *platform*; return the mock that counts activations.'''
        with patch.object(launch_module.QtGui, 'QGuiApplication') as gui, \
                patch.object(QtWidgets.QSplashScreen,
                             'activateWindow') as activate:
            gui.platformName.return_value = platform
            self.run_launch(_Widget)
        return activate

    def test_the_splash_screen_is_activated_for_macos(self):
        self.launch_on('cocoa').assert_called_once_with()

    def test_wayland_is_not_asked_to_activate_the_splash_screen(self):
        # It cannot, and Qt warns: "Wayland does not support
        # QWindow::requestActivate()".
        self.launch_on('wayland').assert_not_called()

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

        def open_slowly(parser=None, cameraID=None):
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

        with patch.object(launch_module.chooser, 'open_camera', open_slowly), \
                patch.object(launch_module.chooser, 'make_tree'), \
                patch.object(launch_module.pg, 'mkQApp'), \
                patch.object(launch_module.pg, 'exec', run), \
                patch.object(launch_module.QtWidgets, 'QShortcut'):
            launch(_Widget, 'Title')
        self.assertEqual(seen['notice'], 'Opening the camera...')
        self.assertEqual(seen['windows'], 0)  # nothing to show yet
        self.assertEqual(seen['splashes'], 0)  # gone once the window shows

    def test_a_camera_that_cannot_open_ends_the_program(self):
        with patch.object(launch_module.chooser, 'open_camera',
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

        def open_slowly(parser=None, cameraID=None):
            time.sleep(0.2)
            return 'noise', camera

        with patch.object(launch_module.chooser, 'open_camera', open_slowly), \
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
                ('QVideo.demos.roidemo', 'ROIDemo'),
                ('QVideo.demos.histogramdemo', 'HistogramDemo'),
                ('QVideo.demos.uniformitydemo', 'UniformityDemo'),
                ('QVideo.demos.circulardemo', 'CircularDemo'),
                ('QVideo.demos.compositedemo', 'CompositeDemo'),
                ('QVideo.demos.trackpydemo', 'TrackpyDemo'),
                ('QVideo.demos.combineddemo', 'CombinedDemo'),
                ('QVideo.demos.yolodemo', 'YoloDemo')]


class TestChooseCamera(unittest.TestCase):

    '''launch() asks which camera when the command line leaves it open.'''

    def launcher(self, found, answer):
        with patch.object(sys, 'argv', ['application', '-c']), \
                patch.object(launch_module.chooser, 'choices',
                             return_value=found), \
                patch.object(launch_module.QtWidgets.QInputDialog,
                             'getItem', return_value=answer) as dialog:
            launcher = launch_module._Launcher(app, _Widget, 'Title', {})
            self.addCleanup(launcher.screen.close)
            with patch.object(launcher, 'fail') as fail:
                result = launcher.choose()
        return launcher, result, dialog, fail

    def test_nothing_to_ask_opens_the_camera_from_the_command_line(self):
        launcher, result, dialog, _ = self.launcher({}, ('', False))
        self.assertTrue(result)
        dialog.assert_not_called()
        self.assertIsNone(launcher.opener.cameraID)

    def test_the_choice_goes_to_the_opener(self):
        found = {0: 'Webcam', 3: 'Other'}
        launcher, result, dialog, _ = self.launcher(
            found, ('Other', True))
        self.assertTrue(result)
        self.assertEqual(launcher.opener.cameraID, 3)
        self.assertEqual(dialog.call_args.args[3], ['Webcam', 'Other'])
        self.assertIn('Multiple', dialog.call_args.args[2])

    def test_cameras_with_one_name_are_told_apart_by_index(self):
        launcher, _, dialog, _ = self.launcher(
            {0: 'Webcam', 1: 'Webcam', 2: 'Other'}, ('Webcam (1)', True))
        self.assertEqual(dialog.call_args.args[3],
                         ['Webcam (0)', 'Webcam (1)', 'Other'])
        self.assertEqual(launcher.opener.cameraID, 1)

    def test_cancelling_ends_the_program(self):
        launcher, result, _, fail = self.launcher(
            {0: 'Webcam', 1: 'Other'}, ('', False))
        self.assertFalse(result)
        fail.assert_called_once_with('No camera was chosen.')


class TestCommandLine(unittest.TestCase):

    '''The command line is read on the main thread, before the interface.

    argparse ends the program on -h or a bad value by raising SystemExit.
    In the thread that opens the camera that only ended the thread, and the
    splash screen waited for a camera that never came (and Qt crashed when
    the program quit).
    '''

    def launch(self, *args: str) -> subprocess.CompletedProcess:
        script = ('from QVideo.lib import launch\n'
                  'from QVideo.QCamcorder import QCamcorder\n'
                  'launch(QCamcorder, "QCamcorder")\n')
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        return subprocess.run([sys.executable, '-c', script, *args],
                              capture_output=True,
                              text=True,
                              timeout=60,
                              env=env)

    def test_help_prints_and_ends(self):
        done = self.launch('-h')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('usage:', done.stdout)
        self.assertNotIn('QBasicTimer', done.stderr)

    def test_version_prints_and_ends(self):
        done = self.launch('--version')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertRegex(done.stdout, r'^QVideo \S+\n$')

    def test_a_bad_log_level_ends_with_a_message(self):
        done = self.launch('--log-level', 'LOUD')
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn('invalid choice', done.stderr)

    def test_help_says_what_the_program_is(self):
        done = self.launch('-h')
        self.assertIn('A widget combining a video screen', done.stdout)

    def test_help_has_groups_examples_and_the_documentation(self):
        out = self.launch('-h').stdout
        for text in ('camera selection:', 'general:', 'examples:',
                     'a simulated camera, with no hardware:',
                     'qvideo.readthedocs.io'):
            with self.subTest(text=text):
                self.assertIn(text, out)



class TestSummary(unittest.TestCase):

    def test_the_first_paragraph_is_one_line(self):
        class Widget:
            '''Live video that wraps
            over two lines.

            More that is not in the summary.
            '''
        self.assertEqual(launch_module.summary(Widget),
                         'Live video that wraps over two lines.')

    def test_a_class_without_a_docstring_has_none(self):
        class Widget:
            pass
        self.assertIsNone(launch_module.summary(Widget))

    def test_every_demo_has_a_summary(self):
        from QVideo import demos
        for name in ('Demo', 'FilterDemo', 'FilterRackDemo', 'HistogramDemo',
                     'UniformityDemo', 'CircularDemo', 'ROIDemo',
                     'TrackpyDemo', 'YoloDemo', 'CompositeDemo',
                     'CombinedDemo'):
            with self.subTest(demo=name):
                self.assertTrue(launch_module.summary(getattr(demos, name)))


class TestConfigureLogging(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger('QVideo')
        self.saved = (self.logger.level, list(self.logger.handlers))
        self.logger.handlers = []
        self.addCleanup(self.restore)

    def restore(self):
        self.logger.setLevel(self.saved[0])
        self.logger.handlers = self.saved[1]

    def test_none_leaves_logging_alone(self):
        from QVideo.lib._launch import configureLogging
        configureLogging(None)
        self.assertEqual(self.logger.level, self.saved[0])
        self.assertEqual(self.logger.handlers, [])

    def test_the_level_is_set_and_a_handler_added(self):
        from QVideo.lib._launch import configureLogging
        configureLogging('DEBUG')
        self.assertEqual(self.logger.level, logging.DEBUG)
        self.assertEqual(len(self.logger.handlers), 1)

    def test_an_existing_handler_is_kept_and_not_doubled(self):
        from QVideo.lib._launch import configureLogging
        mine = logging.NullHandler()
        self.logger.addHandler(mine)
        configureLogging('INFO')
        configureLogging('INFO')
        self.assertEqual(self.logger.handlers, [mine])
        self.assertEqual(self.logger.level, logging.INFO)


def run_as_script(name):
    '''Run module *name* as ``python -m`` would; return the launch mock.'''
    with patch('QVideo.lib.launch') as mock_launch, \
            patch.object(sys, 'argv', [name]), \
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
