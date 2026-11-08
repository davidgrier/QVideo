'''Unit tests for QPyAVWriter.'''
import importlib.util
import tempfile
import unittest
from pathlib import Path
import numpy as np
from unittest.mock import patch
from qtpy import QtWidgets
from QVideo.dvr.QPyAVWriter import QPyAVWriter
from QVideo.dvr.QPyAVReader import QPyAVReader
from QVideo.lib import QVideoWriter
from QVideo.tests.signals import record


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

have_av = importlib.util.find_spec('av') is not None
needs_av = unittest.skipUnless(have_av, 'PyAV is not installed')


class TestQPyAVWriterClass(unittest.TestCase):

    def test_is_subclass_of_qvideowriter(self):
        self.assertTrue(issubclass(QPyAVWriter, QVideoWriter))

    def test_lossless_codecs_for_avi_and_mkv(self):
        self.assertEqual(QPyAVWriter.CODEC_MAP['.avi'][0], 'ffv1')
        self.assertEqual(QPyAVWriter.CODEC_MAP['.mkv'][0], 'ffv1')

    def test_16_bit_avi_uses_the_faster_lossless_codec(self):
        self.assertEqual(QPyAVWriter.CODEC_MAP_GRAY16['.avi'][0], 'ffvhuff')
        self.assertNotIn('.mkv', QPyAVWriter.CODEC_MAP_GRAY16)

    def test_h264_for_mp4(self):
        self.assertEqual(QPyAVWriter.CODEC_MAP['.mp4'][0], 'libx264')

    def test_not_open_before_the_first_frame(self):
        self.assertFalse(QPyAVWriter('test.mkv', fps=30).isOpen())

    def test_pixel_formats_of_the_encoders(self):
        writer = QPyAVWriter('test.mkv', fps=30)
        writer._format = 'rgb24'
        self.assertEqual(writer._pixelFormat('ffv1'), 'bgr0')
        self.assertEqual(writer._pixelFormat('libx264'), 'yuv420p')
        writer._format = 'gray16le'
        self.assertEqual(writer._pixelFormat('ffv1'), 'gray16le')


@needs_av
class TestQPyAVWriter(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(self._clean)

    def _clean(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def frames(self, shape, dtype=np.uint8, n=5):
        rng = np.random.default_rng(0)
        return [rng.integers(0, np.iinfo(dtype).max, shape, dtype=dtype)
                for _ in range(n)]

    def write(self, frames, name='test.mkv'):
        path = str(self.dir / name)
        writer = QPyAVWriter(path, fps=30)
        for frame in frames:
            writer.write(frame)
        writer.close()
        return path

    def read(self, path):
        reader = QPyAVReader(path)
        self.addCleanup(reader.close)
        out = []
        while True:
            ok, frame = reader.read()
            if not ok:
                return out
            out.append(frame)

    def test_every_pixel_comes_back(self):
        cases = {'gray': ((48, 64), np.uint8),
                 'gray16': ((48, 64), np.uint16),
                 'color': ((48, 64, 3), np.uint8)}
        for suffix in ('.mkv', '.avi'):
            for name, (shape, dtype) in cases.items():
                with self.subTest(suffix=suffix, frames=name):
                    frames = self.frames(shape, dtype)
                    back = self.read(self.write(frames, f'{name}{suffix}'))
                    self.assertEqual(len(back), len(frames))
                    for sent, got in zip(frames, back):
                        self.assertEqual(sent.dtype, got.dtype)
                        np.testing.assert_array_equal(sent, got)

    def test_the_codec_follows_the_pixels_and_the_container(self):
        cases = [('.avi', np.uint8, 'ffv1'), ('.avi', np.uint16, 'ffvhuff'),
                 ('.mkv', np.uint8, 'ffv1'), ('.mkv', np.uint16, 'ffv1')]
        for suffix, dtype, codec in cases:
            with self.subTest(suffix=suffix, dtype=dtype.__name__):
                writer = QPyAVWriter(str(self.dir / f'a{suffix}'), fps=30)
                self.addCleanup(writer.close)
                self.assertTrue(
                    writer.open(self.frames((48, 64), dtype)[0]))
                self.assertEqual(writer._stream.codec_context.name, codec)
                writer.close()

    def test_mp4_holds_8_bits_so_deep_frames_are_scaled(self):
        from QVideo.lib.videotypes import FrameInfo
        frames = [np.full((48, 64), 4095, np.uint16) for _ in range(5)]
        writer = QPyAVWriter(str(self.dir / 'deep.mp4'), fps=30)
        with self.assertLogs('QVideo.dvr.QPyAVWriter', 'INFO'):
            writer.open(frames[0])
        for index, frame in enumerate(frames):
            writer._write(frame, FrameInfo(index, 0., levels=(0., 4095.)))
        writer.close()
        back = self.read(str(self.dir / 'deep.mp4'))
        self.assertEqual(len(back), 5)
        self.assertGreater(float(np.mean(back[0])), 200)

    def test_mp4_keeps_the_number_of_frames(self):
        frames = self.frames((48, 64, 3))
        self.assertEqual(len(self.read(self.write(frames, 'a.mp4'))), 5)

    def test_the_file_is_open_after_the_first_frame(self):
        writer = QPyAVWriter(str(self.dir / 'a.mkv'), fps=30)
        writer.write(self.frames((48, 64))[0])
        self.assertTrue(writer.isOpen())
        writer.close()
        self.assertFalse(writer.isOpen())

    def test_unsupported_frames_are_refused(self):
        writer = QPyAVWriter(str(self.dir / 'a.mkv'), fps=30)
        with self.assertLogs('QVideo.dvr.QPyAVWriter', 'WARNING'):
            ok = writer.open(np.zeros((8, 8), np.float32))
        self.assertFalse(ok)

    def test_unsupported_extension_is_refused(self):
        writer = QPyAVWriter(str(self.dir / 'a.xyz'), fps=30)
        with self.assertLogs('QVideo.dvr.QPyAVWriter', 'WARNING'):
            ok = writer.open(self.frames((8, 8))[0])
        self.assertFalse(ok)

    def test_a_file_that_cannot_be_created_is_reported(self):
        writer = QPyAVWriter(str(self.dir / 'missing' / 'a.mkv'), fps=30)
        with self.assertLogs('QVideo.dvr.QPyAVWriter', 'WARNING'):
            ok = writer.open(self.frames((8, 8))[0])
        self.assertFalse(ok)
        self.assertFalse(writer.isOpen())

    def test_a_frame_that_is_not_contiguous_is_written(self):
        frame = self.frames((48, 64))[0]
        back = self.read(self.write([frame.T.T[:, ::-1][:, ::-1]]))
        np.testing.assert_array_equal(back[0], frame)

    def test_close_is_safe_when_nothing_was_written(self):
        QPyAVWriter(str(self.dir / 'a.mkv'), fps=30).close()

    def test_fractional_rates_are_kept(self):
        import av
        path = str(self.dir / 'ntsc.mkv')
        writer = QPyAVWriter(path, fps=29.97)
        for frame in self.frames((16, 16)):
            writer.write(frame)
        writer.close()
        with av.open(path) as container:
            rate = container.streams.video[0].guessed_rate
        self.assertAlmostEqual(float(rate), 29.97, places=2)


class TestQPyAVImport(unittest.TestCase):

    def test_av_is_not_imported_until_a_file_is_opened(self):
        import subprocess
        import sys
        code = ('import sys, QVideo.dvr; '
                'sys.exit(int("av" in sys.modules))')
        result = subprocess.run(
            [sys.executable, '-c', code], capture_output=True,
            env={**__import__('os').environ,
                 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    @needs_av
    def test_av_is_imported_when_the_writer_is_made(self):
        # not on the first frame, when the camera does not wait for it
        import os
        import subprocess
        import sys
        code = ('import sys; from QVideo.dvr import QPyAVWriter; '
                'QPyAVWriter("x.mkv"); sys.exit(int("av" not in sys.modules))')
        result = subprocess.run(
            [sys.executable, '-c', code], capture_output=True,
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr.decode())


if __name__ == '__main__':
    unittest.main()


class TestRemedy(unittest.TestCase):

    def test_16_bit_mkv_suggests_avi_or_hdf5(self):
        writer = QPyAVWriter('x.mkv')
        writer._format = 'gray16le'
        self.assertIn('.avi or .h5', writer.remedy())
        writer._format = 'gray'
        self.assertNotIn('.avi or .h5', writer.remedy())
