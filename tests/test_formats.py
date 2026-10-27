'''Unit tests for dvr.formats, the video formats that can be handled.'''
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from qtpy import QtWidgets
from QVideo.dvr import formats
from QVideo.dvr import QOpenCVWriter, QOpenCVReader, QPyAVWriter, QPyAVReader
from QVideo.lib import QVideoReader, QVideoSource


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestTables(unittest.TestCase):

    def test_the_video_extensions_have_a_writer_and_a_reader(self):
        for suffix in ('.avi', '.mkv', '.mp4'):
            self.assertIn(suffix, formats.Writer)
            self.assertIn(suffix, formats.Reader)

    def test_pyav_is_preferred_when_it_is_installed(self):
        expected = (QPyAVWriter, QPyAVReader) if formats.pyav_available \
            else (QOpenCVWriter, QOpenCVReader)
        self.assertEqual((formats.Writer['.mkv'], formats.Reader['.mkv']),
                         expected)

    def test_hdf5_needs_h5py(self):
        self.assertEqual('.h5' in formats.Writer, formats.h5py_available)
        self.assertEqual('.h5' in formats.Reader, formats.h5py_available)


class TestPreference(unittest.TestCase):
    '''PyAV handles video files if it is installed, else OpenCV.'''

    def names(self, hide_av):
        code = (
            'import importlib.util as u\n'
            'real = u.find_spec\n'
            f'hide = {hide_av!r}\n'
            'u.find_spec = lambda n, *a: None if hide and n == "av" '
            'else real(n, *a)\n'
            'from QVideo.dvr import formats as f\n'
            'print(f.Writer[".mkv"].__name__, f.Reader[".avi"].__name__, '
            'f.Writer[".mp4"].__name__)\n')
        result = subprocess.run(
            [sys.executable, '-c', code], capture_output=True, text=True,
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.split()

    def test_pyav_is_preferred_when_it_is_installed(self):
        if not formats.pyav_available:
            self.skipTest('PyAV is not installed')
        self.assertEqual(self.names(hide_av=False),
                         ['QPyAVWriter', 'QPyAVReader', 'QPyAVWriter'])

    def test_opencv_is_the_fallback(self):
        self.assertEqual(self.names(hide_av=True),
                         ['QOpenCVWriter', 'QOpenCVReader', 'QOpenCVWriter'])


class TestLookup(unittest.TestCase):

    def test_the_class_of_an_extension_is_found(self):
        self.assertIs(formats.writerClass('run.mkv'), formats.Writer['.mkv'])
        self.assertIs(formats.readerClass('dir/run.avi'),
                      formats.Reader['.avi'])

    def test_an_unsupported_extension_says_what_is_supported(self):
        with self.assertRaisesRegex(ValueError, r"'\.xyz'.*\.avi"):
            formats.writerClass('run.xyz')
        with self.assertRaisesRegex(ValueError, r"'\.xyz'.*\.avi"):
            formats.readerClass('run.xyz')

    def test_a_name_without_an_extension_is_unsupported(self):
        with self.assertRaises(ValueError):
            formats.writerClass('run')

    def test_a_registered_class_is_used(self):
        with patch.dict(formats.Writer, {'.fake': object}):
            self.assertIs(formats.writerClass('x.fake'), object)


class TestOpenVideo(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def test_a_missing_file_cannot_be_opened(self):
        with self.assertLogs('QVideo.lib.QVideoReader', 'WARNING'):
            with self.assertRaises(OSError):
                formats.openVideo(str(self.dir / 'missing.mkv'))

    def test_an_unsupported_extension_is_refused(self):
        with self.assertRaises(ValueError):
            formats.openVideo(str(self.dir / 'movie.xyz'))

    def test_an_opened_video_is_the_reader_of_a_source(self):
        video = formats.openVideo(QVideoReader.examplevideo())
        source = QVideoSource(video)
        self.addCleanup(video.close)
        self.assertTrue(source.isOpen())
        self.assertGreater(source.fps, 0)

    def test_the_example_video_opens_as_a_reader(self):
        video = formats.openVideo(QVideoReader.examplevideo())
        self.addCleanup(video.close)
        self.assertIsInstance(video, QVideoReader)
        self.assertTrue(video.isOpen())


class TestFileFilter(unittest.TestCase):

    def test_known_extensions_appear_in_filter(self):
        f = formats.fileFilter(save=True)
        self.assertIn('.avi', f)
        self.assertEqual('.h5' in f, formats.h5py_available)

    def test_lossless_extensions_grouped_under_lossless_label(self):
        f = formats.fileFilter(save=True)
        self.assertIn('Lossless Video', f)
        lossless_group = next(p for p in f.split(';;') if 'Lossless' in p)
        self.assertIn('.avi', lossless_group)
        self.assertIn('.mkv', lossless_group)

    def test_mp4_grouped_under_video_label(self):
        f = formats.fileFilter(save=True)
        video_group = next(p for p in f.split(';;') if p.startswith('Video'))
        self.assertIn('.mp4', video_group)
        self.assertNotIn('.avi', video_group)
        self.assertNotIn('.mkv', video_group)

    def test_lossless_group_precedes_video_group(self):
        f = formats.fileFilter(save=True)
        self.assertLess(f.index('Lossless'), f.index('Video ('))

    def test_the_filter_for_reading_lists_the_readers(self):
        with patch.dict(formats.Reader, {'.only': object}, clear=True):
            self.assertIn('.only', formats.fileFilter(save=False))
            self.assertNotIn('.avi', formats.fileFilter(save=False))

    def test_ungrouped_extension_appears_in_other_group(self):
        with patch.dict(formats.Writer, {'.webm': object}):
            f = formats.fileFilter(save=True)
        self.assertIn('Other files', f)
        self.assertIn('.webm', f)

    def test_no_formats_returns_all_files(self):
        with patch.dict(formats.Writer, {}, clear=True):
            self.assertEqual(formats.fileFilter(save=True), 'All files (*)')


if __name__ == '__main__':
    unittest.main()
