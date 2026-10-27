'''Unit tests for QHDF5Writer.'''
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import h5py
import numpy as np
from unittest.mock import patch
from qtpy import QtWidgets
from QVideo.dvr.QHDF5Writer import QHDF5Writer, FORMAT_VERSION
from QVideo.dvr.QHDF5Reader import QHDF5Reader
from QVideo.lib.videotypes import FrameInfo
from QVideo.tests.signals import record


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

writer_module = sys.modules['QVideo.dvr.QHDF5Writer']  # not the class

_FRAME = np.zeros((48, 64), dtype=np.uint8)


class WriterCase(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = str(Path(folder.name) / 'test.h5')

    def make(self, **kwargs) -> QHDF5Writer:
        writer = QHDF5Writer(self.path, fps=30, **kwargs)
        self.addCleanup(writer.close)
        return writer

    def write(self, frames, infos=None, **kwargs) -> None:
        '''Write *frames*, then close the file.'''
        writer = self.make(**kwargs)
        for i, frame in enumerate(frames):
            info = infos[i] if infos else FrameInfo(i, 100. + i / 30.)
            writer.write(frame, info)
        writer.close()


class TestInit(WriterCase):

    def test_not_open_before_first_frame(self):
        self.assertFalse(self.make().isOpen())

    def test_file_is_none_initially(self):
        self.assertIsNone(self.make()._file)

    def test_zstandard_is_the_default(self):
        with patch.object(writer_module, '_filter') as chosen:
            self.make()
        chosen.assert_called_once_with('zstd')


class TestOpen(WriterCase):

    def test_open_returns_true_and_creates_the_file(self):
        writer = self.make()
        self.assertTrue(writer.open(_FRAME))
        self.assertTrue(writer.isOpen())
        self.assertTrue(Path(self.path).exists())

    def test_open_returns_false_if_the_file_cannot_be_made(self):
        writer = QHDF5Writer(str(Path(self.path).parent / 'no' / 'x.h5'))
        with self.assertLogs('QVideo.dvr.QHDF5Writer', 'WARNING'):
            self.assertFalse(writer.open(_FRAME))
        self.assertFalse(writer.isOpen())

    def test_the_datasets_wait_for_the_first_frame(self):
        writer = self.make()
        writer.open(_FRAME)
        self.assertIsNone(writer._frames)
        self.assertEqual(list(writer._file), [])


class TestLayout(WriterCase):

    def read(self, name):
        with h5py.File(self.path, 'r') as f:
            return f[name][()]

    def test_the_file_holds_the_frames_and_one_array_for_each_metadatum(self):
        self.write([_FRAME] * 3)
        with h5py.File(self.path, 'r') as f:
            self.assertEqual(sorted(f), ['frames', 'hardware_timestamp',
                                         'index', 'timestamp'])
            self.assertEqual(f['frames'].shape, (3,) + _FRAME.shape)
            for name in ('timestamp', 'index', 'hardware_timestamp'):
                self.assertEqual(f[name].shape, (3,))

    def test_the_file_says_which_layout_it_has(self):
        self.write([_FRAME])
        with h5py.File(self.path, 'r') as f:
            self.assertEqual(f.attrs['format_version'], FORMAT_VERSION)

    def test_the_file_records_the_frame_rate_it_was_told(self):
        writer = QHDF5Writer(self.path, fps=30, nskip=3)
        self.addCleanup(writer.close)
        writer.write(_FRAME, FrameInfo(0, 1.))
        writer.close()
        with h5py.File(self.path, 'r') as f:
            self.assertEqual(f.attrs['fps'], 10.)

    def test_every_frame_is_a_chunk_of_its_own(self):
        self.write([_FRAME] * 2)
        with h5py.File(self.path, 'r') as f:
            self.assertEqual(f['frames'].chunks, (1,) + _FRAME.shape)

    def test_frames_are_stored_as_they_are(self):
        for dtype, shape in ((np.uint8, (6, 8)), (np.uint16, (6, 8)),
                             (np.uint8, (6, 8, 3))):
            with self.subTest(dtype=dtype.__name__, shape=shape):
                frames = [np.full(shape, i + 1, dtype) for i in range(3)]
                self.write(frames)
                with h5py.File(self.path, 'r') as f:
                    self.assertEqual(f['frames'].dtype, dtype)
                    np.testing.assert_array_equal(f['frames'][()], frames)

    def test_a_frame_without_capture_info_is_stamped_on_the_spot(self):
        writer = self.make()
        writer.open(_FRAME)
        writer._write(_FRAME)
        writer.close()
        self.assertEqual(len(self.read('timestamp')), 1)

    def test_writing_without_capture_info_stamps_the_frames(self):
        writer = self.make()
        for _ in range(2):
            writer.write(_FRAME)
        writer.close()
        t = self.read('timestamp')
        self.assertEqual(len(t), 2)
        self.assertGreaterEqual(t[1], t[0])


class TestMetadata(WriterCase):

    def test_times_run_from_the_capture_of_the_first_frame(self):
        self.write([_FRAME] * 3, [FrameInfo(0, 10.), FrameInfo(1, 10.5),
                                  FrameInfo(2, 12.)])
        with h5py.File(self.path, 'r') as f:
            np.testing.assert_allclose(f['timestamp'][()], [0., .5, 2.])

    def test_the_start_attribute_is_the_wall_clock_of_the_first_frame(self):
        first = FrameInfo(0, 10.)
        self.write([_FRAME] * 2, [first, FrameInfo(1, 11.)])
        with h5py.File(self.path, 'r') as f:
            self.assertAlmostEqual(f.attrs['Timestamp'], first.wallclock,
                                   delta=0.1)

    def test_the_index_of_each_frame_is_kept(self):
        self.write([_FRAME] * 3, [FrameInfo(4, 1.), FrameInfo(6, 2.),
                                  FrameInfo(9, 3.)])
        with h5py.File(self.path, 'r') as f:
            self.assertEqual(list(f['index'][()]), [4, 6, 9])

    def test_the_hardware_time_is_kept_or_not_a_number(self):
        self.write([_FRAME] * 2, [FrameInfo(0, 1., 7.5), FrameInfo(1, 2.)])
        with h5py.File(self.path, 'r') as f:
            first, second = f['hardware_timestamp'][()]
        self.assertEqual(first, 7.5)
        self.assertTrue(np.isnan(second))

    def test_closing_starts_a_new_file_for_the_next_recording(self):
        writer = self.make()
        writer.write(_FRAME, FrameInfo(0, 10.))
        writer.write(_FRAME, FrameInfo(1, 11.))
        writer.close()
        writer.write(_FRAME, FrameInfo(2, 50.))
        writer.close()
        with h5py.File(self.path, 'r') as f:
            self.assertEqual(f['frames'].shape[0], 1)
            self.assertEqual(f['timestamp'][0], 0.)


class TestCompression(WriterCase):

    def roundtrip(self, frames, **kwargs):
        self.write(frames, **kwargs)
        reader = QHDF5Reader(self.path)
        back = [reader.read()[1] for _ in frames]
        reader.close()  # Windows cannot delete a file that is open
        return back, Path(self.path).stat().st_size

    def frames(self, dtype):
        rng = np.random.default_rng(0)
        high = np.iinfo(dtype).max + 1
        ramp = np.linspace(0, high - 1, 64 * 48).reshape(48, 64)
        return [(ramp + rng.integers(0, 4, ramp.shape)).clip(
            0, high - 1).astype(dtype) for _ in range(4)]

    def test_every_filter_returns_every_pixel(self):
        filters = [None, 'lzf', 'gzip']
        if writer_module.hdf5plugin is not None:
            filters += ['zstd', 'lz4', 'blosc2']
        for dtype in (np.uint8, np.uint16):
            frames = self.frames(dtype)
            for name in filters:
                with self.subTest(dtype=dtype.__name__, compression=name):
                    back, _ = self.roundtrip(frames, compression=name)
                    for sent, got in zip(frames, back):
                        np.testing.assert_array_equal(sent, got)

    def test_compression_makes_the_file_smaller(self):
        frames = [np.zeros((256, 256), np.uint8) for _ in range(4)]
        _, raw = self.roundtrip(frames, compression=None)
        _, packed = self.roundtrip(frames, compression='lzf')
        self.assertLess(packed, raw)

    def test_the_filter_is_applied_to_the_frames_only(self):
        self.write([_FRAME] * 2, compression='lzf')
        with h5py.File(self.path, 'r') as f:
            self.assertEqual(f['frames'].compression, 'lzf')
            self.assertIsNone(f['timestamp'].compression)

    def test_no_compression_gives_no_filter(self):
        self.assertEqual(writer_module._filter(None), {})
        self.write([_FRAME], compression=None)
        with h5py.File(self.path, 'r') as f:
            self.assertIsNone(f['frames'].compression)

    def test_builtin_filters_need_no_plugin(self):
        with patch.object(writer_module, 'hdf5plugin', None):
            self.assertEqual(writer_module._filter('lzf'),
                             {'compression': 'lzf'})
            self.assertEqual(writer_module._filter('gzip')['compression'],
                             'gzip')

    def test_without_the_plugin_frames_are_stored_uncompressed(self):
        with patch.object(writer_module, 'hdf5plugin', None):
            with self.assertLogs('QVideo.dvr.QHDF5Writer', 'INFO'):
                self.assertEqual(writer_module._filter('zstd'), {})


class TestFramesThatDoNotMatch(WriterCase):

    def check(self, other):
        writer = self.make()
        writer.write(_FRAME, FrameInfo(0, 1.))
        finished = record(writer.finished)
        with self.assertLogs('QVideo.dvr.QHDF5Writer', 'WARNING'):
            writer.write(other, FrameInfo(1, 2.))
        writer.close()
        self.assertEqual(len(finished), 1)
        with h5py.File(self.path, 'r') as f:
            self.assertEqual(f['frames'].shape[0], 1)
            self.assertEqual(f['timestamp'].shape[0], 1)

    def test_a_frame_of_another_size_ends_the_recording(self):
        self.check(np.zeros((10, 10), np.uint8))

    def test_a_frame_of_another_type_ends_the_recording(self):
        self.check(np.zeros(_FRAME.shape, np.float32))


class TestFlush(WriterCase):

    def test_a_flush_comes_when_the_interval_has_passed(self):
        writer = self.make()
        with patch.object(writer_module, '_FLUSH_INTERVAL', 0.), \
             patch.object(writer, '_flush') as flush:
            writer.write(_FRAME, FrameInfo(0, 1.))
            writer.write(_FRAME, FrameInfo(1, 2.))
        self.assertEqual(flush.call_count, 2)

    def test_no_flush_comes_before_the_interval_has_passed(self):
        writer = self.make()
        with patch.object(writer, '_flush') as flush:
            for i in range(5):
                writer.write(_FRAME, FrameInfo(i, i / 30.))
        flush.assert_not_called()

    def test_a_flush_covers_every_dataset(self):
        writer = self.make()
        writer.write(_FRAME, FrameInfo(0, 1.))
        with patch.object(h5py.Dataset, 'flush') as flush:
            writer._flush()
        self.assertEqual(flush.call_count, 4)


CRASH = '''
import os, signal, sys
import numpy as np
from qtpy import QtWidgets
from QVideo.dvr import QHDF5Writer
from QVideo.lib.videotypes import FrameInfo
sys.modules['QVideo.dvr.QHDF5Writer']._FLUSH_INTERVAL = 0.
app = QtWidgets.QApplication([])
writer = QHDF5Writer(sys.argv[1], fps=30)
for i in range(40):
    writer.write(np.full((16, 16), i, np.uint8), FrameInfo(i, i / 30.))
os.kill(os.getpid(), signal.SIGKILL)
'''


@unittest.skipIf(sys.platform == 'win32', 'no SIGKILL on Windows')
class TestACrashSpares(WriterCase):
    '''The frames that were flushed survive the death of the program.'''

    def test_a_recording_that_was_killed_can_be_read(self):
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        subprocess.run([sys.executable, '-c', CRASH, self.path], env=env,
                       capture_output=True, timeout=60)
        reader = QHDF5Reader(self.path)
        self.addCleanup(reader.close)
        self.assertTrue(reader.isOpen())
        self.assertEqual(reader.length, 40)
        self.assertEqual(reader.read()[1][0, 0], 0)


class TestClose(WriterCase):

    def test_close_closes_the_file(self):
        writer = self.make()
        writer.write(_FRAME, FrameInfo(0, 1.))
        writer.close()
        self.assertFalse(writer.isOpen())
        self.assertIsNone(writer._file)

    def test_a_closed_file_opens_without_any_special_mode(self):
        self.write([_FRAME] * 2)
        with h5py.File(self.path, 'r') as f:
            self.assertEqual(f['frames'].shape[0], 2)

    def test_close_when_not_open_is_safe(self):
        self.make().close()

    def test_close_twice_is_safe(self):
        writer = self.make()
        writer.write(_FRAME, FrameInfo(0, 1.))
        writer.close()
        writer.close()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
