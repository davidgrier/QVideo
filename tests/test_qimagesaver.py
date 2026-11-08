'''Unit tests for QImageSaver.'''
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from qtpy import QtGui, QtWidgets
from QVideo.lib.QImageSaver import QImageSaver
from QVideo.tests.signals import record


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

DIALOG = 'qtpy.QtWidgets.QFileDialog.getSaveFileName'


class TestQImageSaver(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.saver = QImageSaver(None, self.folder, 'test')
        self.messages = record(self.saver.message)
        self.image = np.arange(24, dtype=np.uint8).reshape(4, 6)

    def stamp(self, text='20260511_120000'):
        return patch('QVideo.lib.QImageSaver.datetime.datetime',
                     **{'now.return_value.strftime.return_value': text})

    def test_the_default_name_has_a_prefix_and_a_timestamp(self):
        with self.stamp():
            path = self.saver.defaultPath()
        self.assertEqual(path, str(self.folder / 'test_20260511_120000.png'))

    def test_an_existing_file_is_not_overwritten(self):
        (self.folder / 'test_20260511_120000.png').touch()
        (self.folder / 'test_20260511_120000_1.png').touch()
        with self.stamp():
            path = self.saver.defaultPath()
        self.assertEqual(Path(path).name, 'test_20260511_120000_2.png')

    def test_a_prefix_can_be_given_for_one_name(self):
        with self.stamp():
            path = self.saver.defaultPath('shot')
        self.assertEqual(Path(path).name, 'shot_20260511_120000.png')
        path = self.saver.save(self.image, prefix='shot')
        self.assertTrue(Path(path).name.startswith('shot_'))

    def test_the_directory_defaults_to_the_current_directory(self):
        self.assertEqual(QImageSaver().directory, Path.cwd())

    def test_save_without_a_name_writes_the_default(self):
        path = self.saver.save(self.image)
        self.assertEqual(Path(path).parent, self.folder)
        self.assertTrue(Path(path).exists())

    def test_save_with_a_name_uses_it(self):
        name = str(self.folder / 'mine.png')
        self.assertEqual(self.saver.save(self.image, name), name)
        loaded = QtGui.QImage(name)
        self.assertEqual(loaded.pixelColor(2, 1).red(), self.image[1, 2])

    def test_a_given_name_is_overwritten(self):
        name = self.folder / 'mine.png'
        name.write_bytes(b'old')
        self.saver.save(self.image, name)
        self.assertGreater(name.stat().st_size, 3)

    def test_success_is_reported(self):
        path = self.saver.save(self.image)
        self.assertEqual(self.messages, [(f'Saved {path}',)])

    def test_failure_is_reported_and_logged(self):
        name = '/nonexistent-folder/image.png'
        with self.assertLogs('QVideo.lib.QImageSaver', 'WARNING'):
            result = self.saver.save(self.image, name)
        self.assertIsNone(result)
        self.assertTrue(
            self.messages[0][0].startswith(f'Could not save {name}: '))

    def test_a_bad_image_is_reported(self):
        with self.assertLogs('QVideo.lib.QImageSaver', 'WARNING'):
            result = self.saver.save(np.zeros((4, 6), np.float32))
        self.assertIsNone(result)
        self.assertIn('unsupported dtype', self.messages[0][0])

    def test_the_dialog_suggests_the_default_name(self):
        with patch(DIALOG, return_value=('', '')) as dialog, self.stamp():
            self.saver.save(self.image, ask=True)
        self.assertEqual(dialog.call_args[0][2],
                         str(self.folder / 'test_20260511_120000.png'))

    def test_the_dialog_suggests_a_given_name(self):
        with patch(DIALOG, return_value=('', '')) as dialog:
            self.saver.save(self.image, 'here.png', ask=True)
        self.assertEqual(dialog.call_args[0][2], 'here.png')

    def test_the_name_from_the_dialog_is_used(self):
        name = str(self.folder / 'chosen.png')
        with patch(DIALOG, return_value=(name, '')):
            self.assertEqual(self.saver.save(self.image, ask=True), name)
        self.assertTrue(Path(name).exists())

    def test_cancelling_the_dialog_saves_and_says_nothing(self):
        with patch(DIALOG, return_value=('', '')):
            self.assertIsNone(self.saver.save(self.image, ask=True))
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual(self.messages, [])

    def test_the_dialog_belongs_to_a_widget_parent(self):
        parent = QtWidgets.QWidget()
        saver = QImageSaver(parent, self.folder)
        with patch(DIALOG, return_value=('', '')) as dialog:
            saver.save(self.image, ask=True)
        self.assertIs(dialog.call_args[0][0], parent)

    def test_the_levels_reach_a_deep_image(self):
        image = np.full((4, 6), 4095, np.uint16)
        path = self.saver.save(image, levels=(0., 4095.))
        self.assertEqual(QtGui.QImage(path).pixelColor(0, 0).red(), 255)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
