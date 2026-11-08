'''Unit tests for what an application remembers.'''
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from qtpy import QtCore, QtWidgets
from QVideo.lib import _settings
from QVideo.lib.QImageSaver import QImageSaver
from QVideo.lib.QSnapshot import QSnapshot
from QVideo.dvr.QDVRWidget import QDVRWidget


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class Remembering(unittest.TestCase):

    '''A named application whose settings are in a temporary file.'''

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.ini = str(self.folder / 'settings.ini')
        patcher = patch.object(_settings, '_open', self.open)
        patcher.start()
        self.addCleanup(patcher.stop)

    def open(self):
        return QtCore.QSettings(self.ini, QtCore.QSettings.Format.IniFormat)


class TestIsNamed(unittest.TestCase):

    def named(self, name):
        return patch.object(_settings.QtCore.QCoreApplication,
                            'applicationName', return_value=name)

    def test_an_application_without_a_name_is_not_named(self):
        with self.named(''):
            self.assertFalse(_settings.isNamed())

    def test_the_name_of_the_interpreter_is_not_a_name(self):
        stem = Path(_settings.sys.executable).stem
        with self.named(stem.upper()):
            self.assertFalse(_settings.isNamed())

    def test_a_name_of_its_own_is_a_name(self):
        with self.named('QCamcorder'):
            self.assertTrue(_settings.isNamed())

    def test_there_are_no_settings_without_a_name(self):
        with self.named(''):
            self.assertIsNone(_settings._open())
            _settings.remember('a/b', 'c')
            self.assertEqual(_settings.recall('a/b', 'none'), 'none')

    def test_the_settings_belong_to_the_application(self):
        with self.named('QCamcorder'):
            settings = _settings._open()
        name = settings.fileName().casefold()
        self.assertIn('qcamcorder', name)
        self.assertIn(_settings.ORGANIZATION.casefold(), name)


class TestRememberRecall(Remembering):

    def test_a_value_comes_back(self):
        _settings.remember('images/directory', '/somewhere')
        self.assertEqual(_settings.recall('images/directory'), '/somewhere')

    def test_the_default_is_returned_for_an_unknown_key(self):
        self.assertEqual(_settings.recall('nothing', 'x'), 'x')

    def test_a_value_that_is_not_text_is_the_default(self):
        settings = self.open()
        settings.setValue('number', 3)
        settings.sync()
        self.assertEqual(_settings.recall('number', 'x'), 'x')

    def test_a_file_that_cannot_be_written_is_logged_not_raised(self):
        blocker = self.folder / 'blocker'
        blocker.touch()  # a folder cannot be made inside a file
        self.ini = str(blocker / 'settings.ini')
        with self.assertLogs('QVideo.lib._settings', 'WARNING'):
            _settings.remember('a', 'b')


class TestImageSaverRemembers(Remembering):

    def setUp(self):
        super().setUp()
        self.image = np.zeros((4, 6), np.uint8)
        self.target = self.folder / 'pictures'
        self.target.mkdir()

    def test_it_forgets_without_a_key(self):
        saver = QImageSaver(None, self.target)
        saver.save(self.image)
        self.assertEqual(_settings.recall('images/directory'), '')

    def test_the_directory_of_a_file_is_remembered(self):
        saver = QImageSaver(None, self.folder, key='images')
        saver.save(self.image, self.target / 'a.png')
        self.assertEqual(_settings.recall('images/directory'),
                         str(self.target.resolve()))
        self.assertEqual(saver.directory, self.target.resolve())

    def test_the_next_session_starts_there(self):
        QImageSaver(None, self.folder, key='images').save(
            self.image, self.target / 'a.png')
        again = QImageSaver(None, self.folder, key='images')
        self.assertEqual(again.directory, self.target.resolve())
        self.assertEqual(Path(again.defaultPath()).parent,
                         self.target.resolve())

    def test_a_directory_that_has_gone_is_not_used(self):
        _settings.remember('images/directory', str(self.folder / 'gone'))
        saver = QImageSaver(None, self.folder, key='images')
        self.assertEqual(saver.directory, self.folder)

    def test_a_failed_save_remembers_nothing(self):
        saver = QImageSaver(None, self.folder, key='images')
        with self.assertLogs('QVideo.lib.QImageSaver', 'WARNING'):
            saver.save(np.zeros((4, 6), np.float32), self.target / 'a.png')
        self.assertEqual(_settings.recall('images/directory'), '')

    def test_a_snapshot_remembers_where_it_saved(self):
        parent = QtWidgets.QWidget()
        snap = QSnapshot(parent)
        snap.saver.save(self.image, self.target / 'a.png')
        self.assertEqual(_settings.recall('images/directory'),
                         str(self.target.resolve()))


class TestDVRRemembers(Remembering):

    def make(self, key='dvr'):
        widget = QDVRWidget(key=key)
        self.addCleanup(widget.deleteLater)
        return widget

    def test_it_starts_with_the_default_file(self):
        self.assertEqual(self.make().filename,
                         str(Path.home() / QDVRWidget.FILENAME))

    def test_the_file_of_the_last_session_is_offered(self):
        name = str(self.folder / 'run.mkv')
        _settings.remember('dvr/filename', name)
        self.assertEqual(self.make().filename, name)

    def test_a_file_in_a_directory_that_has_gone_is_not_offered(self):
        _settings.remember('dvr/filename', str(self.folder / 'x' / 'a.mkv'))
        self.assertEqual(self.make().filename,
                         str(Path.home() / QDVRWidget.FILENAME))

    def test_without_a_key_it_remembers_nothing(self):
        _settings.remember('dvr/filename', str(self.folder / 'run.mkv'))
        widget = self.make(key=None)
        self.assertEqual(widget.filename,
                         str(Path.home() / QDVRWidget.FILENAME))
        widget._remember()
        self.assertEqual(_settings.recall('dvr/filename'),
                         str(self.folder / 'run.mkv'))

    def test_a_typed_file_is_remembered_when_a_recording_starts(self):
        widget = self.make()
        name = str(self.folder / 'typed.mkv')
        widget.filename = name
        with patch.object(widget, '_accepts', return_value=True), \
                patch.object(widget, '_mayRecord', return_value=True), \
                patch.object(widget.recorder, 'start'), \
                patch.object(widget, '_display'), \
                patch.object(QDVRWidget, 'source',
                             new=property(lambda self: object())), \
                patch.object(widget, 'isPlaying', return_value=False), \
                patch.object(widget, 'isRecording', return_value=False):
            widget.record()
        self.assertEqual(_settings.recall('dvr/filename'), name)

    def test_the_file_is_remembered_when_playback_starts(self):
        widget = self.make()
        name = self.folder / 'play.mkv'
        name.touch()
        widget.filename = str(name)
        with patch.object(widget.playback, 'start'), \
                patch.object(widget, 'isPaused', return_value=False), \
                patch.object(widget, 'isRecording', return_value=False), \
                patch.object(widget, 'isPlaying', return_value=False):
            widget.play()
        self.assertEqual(_settings.recall('dvr/filename'), str(name))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
