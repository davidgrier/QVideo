'''Unit tests for QHDF5Reader.'''
import tempfile
import unittest
from pathlib import Path
import h5py
import numpy as np
from unittest.mock import patch
from qtpy import QtWidgets
from QVideo.dvr.QHDF5Reader import QHDF5Reader
from QVideo.dvr.QHDF5Writer import QHDF5Writer
from QVideo.lib.videotypes import FrameInfo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

SHAPE = (48, 64)  # not square, so that width and height differ


def frames(n: int) -> list[np.ndarray]:
    '''Frames that are filled with their own index.'''
    return [np.full(SHAPE, i, np.uint8) for i in range(n)]


class ReaderCase(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = str(Path(folder.name) / 'test.h5')

    def record(self, n: int = 10, fps: float = 30.) -> str:
        '''Write *n* frames at *fps*, as the writer does.'''
        writer = QHDF5Writer(self.path, fps=fps)
        for i, frame in enumerate(frames(n)):
            writer.write(frame, FrameInfo(i, 100. + i / fps))
        writer.close()
        return self.path

    def version1(self, times: list[float]) -> str:
        '''Make a file of the first layout: a dataset for each frame.'''
        with h5py.File(self.path, 'w', libver='latest',
                       track_order=True) as f:
            f.attrs['Timestamp'] = 1.
            group = f.create_group('images')
            for i, t in enumerate(times):
                group.create_dataset(f'{t:.9f}',
                                     data=np.full(SHAPE, i, np.uint8))
        return self.path

    def open(self, path: str | None = None) -> QHDF5Reader:
        reader = QHDF5Reader(path or self.path)
        self.addCleanup(reader.close)  # Windows cannot delete open files
        return reader


class TestInit(ReaderCase):

    def test_opens_on_init(self):
        self.record()
        self.assertTrue(self.open().isOpen())

    def test_init_fails_if_there_is_no_file(self):
        self.assertFalse(self.open().isOpen())

    def test_init_fails_on_a_file_without_frames(self):
        QHDF5Writer(self.path).open(np.zeros(SHAPE, np.uint8))
        self.assertFalse(self.open().isOpen())

    def test_init_fails_on_a_file_that_is_not_a_video(self):
        with h5py.File(self.path, 'w') as f:
            f.create_dataset('x', data=[1, 2, 3])
        self.assertFalse(self.open().isOpen())

    def test_init_fails_on_a_dataset_with_no_frames(self):
        with h5py.File(self.path, 'w') as f:
            f.create_dataset('frames', (0,) + SHAPE, 'u1',
                             maxshape=(None,) + SHAPE)
            f.create_dataset('timestamp', (0,), 'f8', maxshape=(None,))
        self.assertFalse(self.open().isOpen())

    def test_init_fails_on_a_layout_from_the_future(self):
        self.record()
        with h5py.File(self.path, 'a') as f:
            f.attrs['format_version'] = 99
        with self.assertLogs('QVideo.dvr.QHDF5Reader', 'WARNING') as logs:
            reader = self.open()
        self.assertFalse(reader.isOpen())
        self.assertIn('format version 99', logs.output[0])

    def test_init_fails_on_frames_that_cannot_be_decoded(self):
        self.record()
        with patch.object(QHDF5Reader, '_frame', side_effect=OSError):
            with self.assertLogs('QVideo.dvr.QHDF5Reader', 'WARNING') as logs:
                reader = self.open()
        self.assertFalse(reader.isOpen())
        self.assertIn('hdf5plugin', logs.output[0])


class TestProperties(ReaderCase):

    def test_framenumber_starts_at_zero(self):
        self.record()
        self.assertEqual(self.open().framenumber, 0)

    def test_length(self):
        self.record(7)
        self.assertEqual(self.open().length, 7)

    def test_width_and_height_come_from_the_frames(self):
        self.record()
        reader = self.open()
        self.assertEqual((reader.height, reader.width), SHAPE)

    def test_fps_is_computed_from_the_timestamps(self):
        for fps in (30., 12.5):
            with self.subTest(fps=fps):
                self.record(fps=fps)
                reader = self.open()
                self.assertAlmostEqual(reader.fps, fps, places=3)
                reader.close()

    def test_fps_of_a_single_frame_is_the_default(self):
        self.record(1)
        self.assertEqual(self.open().fps, 30.)

    def test_fps_of_frames_with_no_time_between_them_is_the_default(self):
        writer = QHDF5Writer(self.path)
        for i in range(3):
            writer.write(frames(1)[0], FrameInfo(i, 5.))
        writer.close()
        self.assertEqual(self.open().fps, 30.)

    def test_the_times_of_the_frames_are_available(self):
        self.record(4, fps=10.)
        np.testing.assert_allclose(self.open().timestamps,
                                   [0., .1, .2, .3])


class TestRead(ReaderCase):

    def test_read_returns_the_frames_in_order(self):
        self.record(5)
        reader = self.open()
        for i in range(5):
            ok, frame = reader.read()
            self.assertTrue(ok)
            np.testing.assert_array_equal(frame, frames(5)[i])
        self.assertEqual(reader.framenumber, 5)

    def test_read_past_the_end_returns_false_and_none(self):
        self.record(2)
        reader = self.open()
        reader.read()
        reader.read()
        self.assertEqual(reader.read(), (False, None))

    def test_the_frames_are_not_kept_by_the_reader(self):
        self.record(2)
        reader = self.open()
        _, frame = reader.read()
        frame[...] = 99
        np.testing.assert_array_equal(self.open().read()[1], frames(1)[0])


class TestSeek(ReaderCase):

    def test_seek_then_read_goes_on_from_there(self):
        self.record(6)
        reader = self.open()
        reader.seek(4)
        self.assertEqual(reader.framenumber, 4)
        self.assertEqual(reader.read()[1][0, 0], 4)

    def test_seek_to_the_start_rewinds(self):
        self.record(6)
        reader = self.open()
        reader.read()
        reader.read()
        reader.seek(0)
        self.assertEqual(reader.read()[1][0, 0], 0)


class TestVersion1(ReaderCase):
    '''Files of the first layout are read as they always were.'''

    def test_the_frames_follow_the_times_in_their_names(self):
        # sorted as text, 10.0 would come before 2.0
        self.version1([0., 2., 10., 4.])
        reader = self.open()
        self.assertTrue(reader.isOpen())
        order = [reader.read()[1][0, 0] for _ in range(4)]
        self.assertEqual(order, [0, 1, 3, 2])
        np.testing.assert_allclose(reader.timestamps, [0., 2., 4., 10.])

    def test_length_size_and_rate(self):
        self.version1([0., 1., 2., 3.])
        reader = self.open()
        self.assertEqual(reader.length, 4)
        self.assertEqual((reader.height, reader.width), SHAPE)
        self.assertAlmostEqual(reader.fps, 1.)

    def test_a_group_without_frames_is_not_a_video(self):
        self.version1([])
        self.assertFalse(self.open().isOpen())


class TestACutShortFile(ReaderCase):

    def test_a_frame_without_a_time_is_left_out(self):
        with h5py.File(self.path, 'w') as f:
            f.create_dataset('frames', data=np.stack(frames(5)))
            f.create_dataset('timestamp', data=np.arange(4.))
        reader = self.open()
        self.assertEqual(reader.length, 4)
        self.assertEqual(len(reader.timestamps), 4)

    def test_a_file_that_the_writer_still_holds_can_be_read(self):
        writer = QHDF5Writer(self.path, fps=30)
        self.addCleanup(writer.close)
        for i, frame in enumerate(frames(3)):
            writer.write(frame, FrameInfo(i, i / 30.))
        writer._flush()
        reader = self.open()
        self.assertTrue(reader.isOpen())
        self.assertEqual(reader.length, 3)


class TestClose(ReaderCase):

    def test_close_closes_the_file(self):
        self.record()
        reader = self.open()
        file = reader._file
        reader.close()
        self.assertFalse(reader.isOpen())
        self.assertFalse(bool(file))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
