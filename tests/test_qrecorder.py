'''Unit tests for QRecorder.'''
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from qtpy import QtTest, QtWidgets
from QVideo.dvr import QRecorder, formats
from QVideo.dvr.QHDF5Writer import QHDF5Writer
from QVideo.lib.videotypes import FrameInfo
from QVideo.tests.fakes import FakeSource, FakeWriter, until
from QVideo.tests.signals import record


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((4, 4), dtype=np.uint8)


class RecorderCase(unittest.TestCase):

    def setUp(self):
        FakeWriter.made = []
        patcher = patch.dict(formats.Writer, {'.fake': FakeWriter})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.source = FakeSource()
        self.recorder = QRecorder(self.source)
        self.addCleanup(self.recorder.stop)

    @property
    def writer(self):
        return FakeWriter.made[-1]


class TestStart(RecorderCase):

    def test_it_is_not_recording_at_first(self):
        self.assertFalse(self.recorder.isRecording())

    def test_starting_begins_a_recording(self):
        on = record(self.recorder.recording)
        self.recorder.start('x.fake')
        self.assertTrue(self.recorder.isRecording())
        self.assertEqual(on, [(True,)])

    def test_the_writer_is_told_the_rate_and_the_number_of_frames(self):
        self.recorder.start('x.fake', nframes=7, nskip=3)
        self.assertEqual(self.writer.filename, 'x.fake')
        self.assertEqual(self.writer.fps, 30.)
        self.assertEqual((self.writer.target, self.writer.nskip), (7, 3))

    def test_the_length_and_the_rate_are_those_of_the_recording(self):
        self.recorder.start('x.fake', nframes=7, nskip=3)
        self.assertEqual(self.recorder.nframes, 7)
        self.assertAlmostEqual(self.recorder.rate, 10.)

    def test_without_a_source_it_is_an_error(self):
        with self.assertRaisesRegex(RuntimeError, 'no source'):
            QRecorder().start('x.fake')

    def test_a_second_recording_cannot_start_over_the_first(self):
        self.recorder.start('x.fake')
        with self.assertRaisesRegex(RuntimeError, 'already'):
            self.recorder.start('y.fake')

    def test_an_unsupported_extension_is_an_error_and_starts_nothing(self):
        with self.assertRaises(ValueError):
            self.recorder.start('x.xyz')
        self.assertFalse(self.recorder.isRecording())
        self.assertEqual(FakeWriter.made, [])

    def test_the_frame_rate_is_read_once(self):
        reads = []
        FakeSource.fps = property(lambda s: reads.append(1) or 30.)
        self.addCleanup(delattr, FakeSource, 'fps')
        self.recorder.start('x.fake')
        reads.clear()
        self.source.emit(20)
        self.recorder.stop()
        self.assertEqual(reads, [])


class TestRecording(RecorderCase):

    def test_the_frames_are_written_on_a_thread_of_their_own(self):
        self.recorder.start('x.fake')
        self.source.emit(3)
        self.recorder.stop()
        self.assertEqual(self.writer.written, 3)
        self.assertNotIn(threading.main_thread(), self.writer.threads)

    def test_the_number_of_frames_recorded_is_reported(self):
        numbers = record(self.recorder.frameNumber)
        self.recorder.start('x.fake')
        self.source.emit(3)
        for _ in range(500):  # the counts arrive through the event loop
            if len(numbers) == 3:
                break
            QtTest.QTest.qWait(10)
        self.recorder.stop()
        self.assertEqual(numbers, [(1,), (2,), (3,)])

    def test_the_recording_ends_by_itself_with_the_last_frame(self):
        off = record(self.recorder.recording)
        self.recorder.start('x.fake', nframes=4)
        self.source.emit(6)  # the fifth tells the writer that it is done
        self.assertTrue(until(lambda: not self.recorder.isRecording()))
        self.assertEqual(self.writer.written, 4)
        self.assertEqual(off, [(True,), (False,)])

    def test_stopping_writes_the_frames_that_were_captured(self):
        self.recorder.start('x.fake')
        self.source.emit(50)
        self.recorder.stop()
        self.assertEqual(self.writer.written, 50)
        self.assertTrue(self.writer.closed)

    def test_stopping_twice_is_safe(self):
        off = record(self.recorder.recording)
        self.recorder.start('x.fake')
        self.recorder.stop()
        self.recorder.stop()
        self.assertEqual(off, [(True,), (False,)])

    def test_stopping_without_a_recording_is_safe(self):
        self.recorder.stop()

    def test_stopping_is_safe_when_signals_are_already_disconnected(self):
        self.recorder.start('x.fake')
        self.source.newFrame.disconnect(self.writer.write)
        self.recorder.stop()
        self.assertFalse(self.recorder.isRecording())

    def test_a_stopped_recording_takes_no_more_frames(self):
        self.recorder.start('x.fake')
        self.recorder.stop()
        self.source.emit(5)
        self.assertEqual(self.writer.written, 0)

    def test_another_recording_can_follow(self):
        for _ in range(2):
            self.recorder.start('x.fake')
            self.source.emit(2)
            self.recorder.stop()
        self.assertEqual([w.written for w in FakeWriter.made], [2, 2])

    def test_changing_the_source_stops_the_recording(self):
        self.recorder.start('x.fake')
        self.recorder.source = FakeSource()
        self.assertFalse(self.recorder.isRecording())
        self.assertTrue(self.writer.closed)


class TestOverwrite(RecorderCase):

    def setUp(self):
        super().setUp()
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = self.dir / 'x.fake'

    def test_a_new_file_is_recorded(self):
        self.recorder.start(str(self.path))
        self.assertTrue(self.recorder.isRecording())

    def test_an_existing_file_is_not_replaced_by_default(self):
        self.path.write_text('precious')
        with self.assertRaisesRegex(FileExistsError, 'overwrite=True'):
            self.recorder.start(str(self.path))
        self.assertFalse(self.recorder.isRecording())
        self.assertEqual(FakeWriter.made, [])
        self.assertEqual(self.path.read_text(), 'precious')

    def test_an_existing_file_is_replaced_on_request(self):
        self.path.write_text('old')
        self.recorder.start(str(self.path), overwrite=True)
        self.assertTrue(self.recorder.isRecording())


class TestFallingBehind(RecorderCase):

    def watching(self, **kwargs):
        recorder = QRecorder(self.source, **kwargs)
        self.addCleanup(recorder.stop)
        recorder.start('x.fake')
        self.writer.received = FrameInfo(0, 10.)
        return recorder

    def capture(self, recorder, t):
        recorder._monitor.check(_FRAME, FrameInfo(1, t))

    def test_a_writer_keeping_up_is_left_alone(self):
        recorder = self.watching()
        self.capture(recorder, 10.5)
        self.assertTrue(recorder.isRecording())

    def test_falling_behind_stops_the_recording_by_default(self):
        recorder = self.watching()
        with self.assertLogs('QVideo.dvr.QRecorder', 'ERROR'):
            self.capture(recorder, 12.)
        self.assertFalse(recorder.isRecording())

    def test_the_reason_says_how_far_and_what_to_try(self):
        recorder = self.watching()
        reasons = record(recorder.stopped)
        with self.assertLogs('QVideo.dvr.QRecorder', 'ERROR') as logs:
            self.capture(recorder, 12.)
        reason = reasons[0][0]
        self.assertIn('2.0 s behind', reason)
        self.assertIn('record to .h5', reason)
        self.assertIn('lower the frame size or rate', reason)
        self.assertIn(reason, logs.output[0])

    def test_behind_is_reported_before_the_recording_stops(self):
        recorder = self.watching()
        states = []
        recorder.behind.connect(lambda lag: states.append(
            recorder.isRecording()))
        with self.assertLogs('QVideo.dvr.QRecorder', 'ERROR'):
            self.capture(recorder, 12.)
        self.assertEqual(states, [True])

    def test_recording_continues_when_stopping_is_disabled(self):
        recorder = self.watching(stopWhenBehind=False)
        stops = record(recorder.stopped)
        self.capture(recorder, 12.)
        self.assertTrue(recorder.isRecording())
        self.assertEqual(stops, [])

    def test_the_backlog_is_reported(self):
        recorder = self.watching(stopWhenBehind=False)
        fractions = record(recorder.backlog)
        self.capture(recorder, 10.5)
        self.assertEqual(fractions, [(0.5,)])

    def test_the_limits_reach_the_monitor(self):
        recorder = QRecorder(self.source, lagLimit=3., maxMemory=123)
        self.addCleanup(recorder.stop)
        with patch.object(recorder._monitor, 'start') as start:
            recorder.start('x.fake')
        start.assert_called_once_with(self.writer, 30., 3., 123)

    def test_a_larger_limit_allows_a_larger_lag(self):
        recorder = self.watching(lagLimit=5.)
        self.capture(recorder, 12.)
        self.assertTrue(recorder.isRecording())

    def test_a_frame_that_arrives_after_stopping_is_harmless(self):
        recorder = self.watching()
        recorder.stop()
        self.capture(recorder, 99.)


class TestRemedy(RecorderCase):

    def test_a_video_writer_without_pyav_suggests_installing_it(self):
        with patch.object(formats, 'pyav_available', False):
            self.assertIn('install QVideo[av]', self.recorder._remedy())
        with patch.object(formats, 'pyav_available', True):
            self.assertNotIn('QVideo[av]', self.recorder._remedy())

    def test_without_h5py_it_says_how_to_record_to_hdf5(self):
        without = {k: v for k, v in formats.Writer.items() if k != '.h5'}
        with patch.object(formats, 'Writer', without):
            remedy = self.recorder._remedy()
        self.assertIn('install QVideo[dvr] to record to .h5', remedy)

    def test_an_hdf5_recording_suggests_a_faster_disk(self):
        self.recorder._writer = QHDF5Writer('test.h5', fps=30)
        remedy = self.recorder._remedy()
        self.recorder._writer = None
        self.assertIn('faster disk', remedy)
        self.assertNotIn('record to .h5', remedy)


if __name__ == '__main__':
    unittest.main()
