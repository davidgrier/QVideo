'''Unit tests for QPyAVReader.'''
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
import numpy as np
from qtpy import QtWidgets
from QVideo.dvr.QPyAVWriter import QPyAVWriter
from QVideo.dvr.QPyAVReader import QPyAVReader
from QVideo.lib import QVideoReader


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

have_av = importlib.util.find_spec('av') is not None
needs_av = unittest.skipUnless(have_av, 'PyAV is not installed')


class TestQPyAVReaderClass(unittest.TestCase):

    def test_is_subclass_of_qvideoreader(self):
        self.assertTrue(issubclass(QPyAVReader, QVideoReader))


@needs_av
class TestQPyAVReader(unittest.TestCase):

    N = 30

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def video(self, name='test.mkv', shape=(48, 64), dtype=np.uint8):
        '''A file of frames with a different brightness each.'''
        path = str(self.dir / name)
        writer = QPyAVWriter(path, fps=30)
        step = max(1, int(np.iinfo(dtype).max) // (self.N + 1))
        self.frames = [np.full(shape, step * i, dtype)
                       for i in range(self.N)]
        for frame in self.frames:
            writer.write(frame)
        writer.close()
        reader = QPyAVReader(path)
        self.addCleanup(reader.close)
        return reader

    def test_opens_a_file(self):
        self.assertTrue(self.video().isOpen())

    def test_does_not_open_a_file_that_is_not_video(self):
        path = self.dir / 'text.mkv'
        path.write_text('not a video')
        with self.assertLogs('QVideo.lib.QVideoReader', 'WARNING'):
            reader = QPyAVReader(str(path))
        self.assertFalse(reader.isOpen())

    def test_does_not_open_a_missing_file(self):
        with self.assertLogs('QVideo.lib.QVideoReader', 'WARNING'):
            reader = QPyAVReader(str(self.dir / 'missing.mkv'))
        self.assertFalse(reader.isOpen())

    def test_describes_the_video(self):
        for name in ('a.mkv', 'a.avi', 'a.mp4'):
            with self.subTest(name):
                reader = self.video(name)
                self.assertEqual(reader.length, self.N)
                self.assertEqual(reader.fps, 30.)
                self.assertEqual((reader.width, reader.height), (64, 48))

    def test_shape_is_width_by_height(self):
        shape = self.video().shape
        self.assertEqual((shape.width(), shape.height()), (64, 48))

    def test_reads_every_frame_in_order(self):
        reader = self.video()
        for i in range(self.N):
            ok, frame = reader.read()
            self.assertTrue(ok)
            np.testing.assert_array_equal(frame, self.frames[i])
        self.assertEqual(reader.framenumber, self.N)

    def test_reading_past_the_end_fails(self):
        reader = self.video()
        for _ in range(self.N):
            reader.read()
        self.assertEqual(reader.read(), (False, None))

    def test_returns_16_bit_gray_as_16_bit(self):
        reader = self.video(dtype=np.uint16)
        ok, frame = reader.read()
        self.assertEqual(frame.dtype, np.uint16)
        np.testing.assert_array_equal(frame, self.frames[0])

    def test_returns_color_as_rgb(self):
        reader = self.video(shape=(48, 64, 3))
        ok, frame = reader.read()
        self.assertEqual(frame.shape, (48, 64, 3))

    def test_seek_is_exact_in_lossless_files(self):
        reader = self.video()
        for target in (0, 17, 5, self.N - 1, 23, 24):
            reader.seek(target)
            self.assertEqual(reader.framenumber, target)
            ok, frame = reader.read()
            np.testing.assert_array_equal(frame, self.frames[target])
            self.assertEqual(reader.framenumber, target + 1)

    def test_seek_lands_on_the_frame_in_a_lossy_file(self):
        reader = self.video('a.mp4')
        for target in (0, 17, 5, self.N - 1, 23):
            reader.seek(target)
            ok, frame = reader.read()
            self.assertLess(abs(float(frame.mean())
                                - float(self.frames[target][0, 0])), 6)

    def test_seek_after_the_end_starts_again(self):
        reader = self.video()
        while reader.read()[0]:
            pass
        reader.seek(3)
        np.testing.assert_array_equal(reader.read()[1], self.frames[3])

    def test_rewind_returns_to_the_first_frame(self):
        reader = self.video()
        for _ in range(5):
            reader.read()
        reader.rewind()
        np.testing.assert_array_equal(reader.read()[1], self.frames[0])

    def test_close_closes_the_file(self):
        reader = self.video()
        reader.close()
        self.assertFalse(reader.isOpen())


if __name__ == '__main__':
    unittest.main()
