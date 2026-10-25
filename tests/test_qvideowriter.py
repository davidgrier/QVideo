'''Unit tests for QVideoWriter.'''
import unittest
import numpy as np
from qtpy import QtWidgets, QtTest
from QVideo.lib.QVideoWriter import QVideoWriter
from QVideo.lib.videotypes import FrameInfo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640), dtype=np.uint8)


class _ConcreteWriter(QVideoWriter):
    '''Minimal concrete subclass for testing the base-class write() slot.'''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._open = False
        self._written = []
        self._infos = []

    def open(self, frame):
        self._open = True
        return True

    def isOpen(self):
        return self._open

    def _write(self, frame, info):
        self._written.append(frame.copy())
        self._infos.append(info)

    def close(self):
        self._open = False


class _FailingWriter(_ConcreteWriter):
    '''Writer whose open() always fails.'''

    def open(self, frame):
        return False


class _SuperCallingWriter(QVideoWriter):
    '''Concrete writer that delegates every abstract method to super(),
    exercising the abstract-method bodies in QVideoWriter.'''

    def open(self, frame):
        return super().open(frame)

    def isOpen(self):
        return super().isOpen()

    def _write(self, frame, info):
        return super()._write(frame, info)

    def close(self):
        return super().close()


class TestQVideoWriterFrameInfo(unittest.TestCase):

    def test_info_is_passed_to_internal_write(self):
        w = _ConcreteWriter('out.avi')
        info = FrameInfo(7, 12.5)
        w.write(_FRAME, info)
        self.assertIs(w._infos[0], info)

    def test_missing_info_is_replaced_by_current_stamp(self):
        w = _ConcreteWriter('out.avi')
        w.write(_FRAME)
        self.assertIsInstance(w._infos[0], FrameInfo)

    def test_slot_accepts_signal_with_info(self):
        from qtpy import QtCore
        w = _ConcreteWriter('out.avi')

        class Emitter(QtCore.QObject):
            newFrame = QtCore.Signal(np.ndarray, object)
        e = Emitter()
        e.newFrame.connect(w.write)
        info = FrameInfo(1, 2.)
        e.newFrame.emit(_FRAME, info)
        self.assertIs(w._infos[0], info)


class TestQVideoWriterSignals(unittest.TestCase):

    def test_slot_accepts_a_one_argument_signal(self):
        from qtpy import QtCore

        class Emitter(QtCore.QObject):
            newFrame = QtCore.Signal(np.ndarray)
        w = _ConcreteWriter('out.avi')
        e = Emitter()
        e.newFrame.connect(w.write)
        e.newFrame.emit(_FRAME)
        self.assertEqual(len(w._written), 1)


class TestQVideoWriterInit(unittest.TestCase):

    def test_filename_stored(self):
        w = _ConcreteWriter('out.avi')
        self.assertEqual(w.filename, 'out.avi')

    def test_default_fps(self):
        w = _ConcreteWriter('out.avi')
        self.assertEqual(w.fps, 24)

    def test_custom_fps(self):
        w = _ConcreteWriter('out.avi', fps=60)
        self.assertEqual(w.fps, 60)

    def test_framenumber_starts_at_zero(self):
        w = _ConcreteWriter('out.avi')
        self.assertEqual(w.framenumber, 0)

    def test_default_nskip(self):
        w = _ConcreteWriter('out.avi')
        self.assertEqual(w.nskip, 1)

    def test_custom_nskip(self):
        w = _ConcreteWriter('out.avi', nskip=2)
        self.assertEqual(w.nskip, 2)

    def test_default_nframes(self):
        w = _ConcreteWriter('out.avi')
        self.assertEqual(w.target, 10_000)

    def test_custom_nframes(self):
        w = _ConcreteWriter('out.avi', nframes=50)
        self.assertEqual(w.target, 50)

    def test_blank_false_initially(self):
        w = _ConcreteWriter('out.avi')
        self.assertFalse(w.blank)


class TestQVideoWriterWriteOpen(unittest.TestCase):
    '''Tests for the open-on-first-write path.'''

    def test_write_calls_open_when_closed(self):
        w = _ConcreteWriter('out.avi')
        w.write(_FRAME)
        self.assertTrue(w.isOpen())

    def test_write_records_the_frame_that_opens_the_file(self):
        w = _ConcreteWriter('out.avi')
        w.write(_FRAME)
        self.assertEqual(len(w._written), 1)

    def test_write_open_failure_emits_finished(self):
        w = _FailingWriter('out.avi')
        spy = QtTest.QSignalSpy(w.finished)
        with self.assertLogs('QVideo.lib.QVideoWriter', level='WARNING'):
            w.write(_FRAME)
        self.assertEqual(len(spy), 1)

    def test_write_open_failure_logs_filename(self):
        w = _FailingWriter('out.avi')
        with self.assertLogs('QVideo.lib.QVideoWriter', level='WARNING') as cm:
            w.write(_FRAME)
        self.assertTrue(any('out.avi' in msg for msg in cm.output))

    def test_write_open_failure_does_not_leave_open(self):
        w = _FailingWriter('out.avi')
        with self.assertLogs('QVideo.lib.QVideoWriter', level='WARNING'):
            w.write(_FRAME)
        self.assertFalse(w.isOpen())


class TestQVideoWriterWriteFrame(unittest.TestCase):
    '''Tests for recording frames.'''

    def _feed(self, w, n):
        '''Send *n* frames numbered from 0; return the numbers written.'''
        for i in range(n):
            w.write(np.full_like(_FRAME, i))
        return [int(f[0, 0]) for f in w._written]

    def test_write_calls_internal_write(self):
        w = _ConcreteWriter('out.avi')
        w.write(_FRAME)
        self.assertEqual(len(w._written), 1)

    def test_write_increments_framenumber(self):
        w = _ConcreteWriter('out.avi')
        w.write(_FRAME)
        self.assertEqual(w.framenumber, 1)

    def test_write_emits_frame_number(self):
        w = _ConcreteWriter('out.avi')
        spy = QtTest.QSignalSpy(w.frameNumber)
        w.write(_FRAME)
        self.assertEqual(len(spy), 1)
        self.assertEqual(spy[0][0], 1)

    def test_multiple_writes_accumulate_framenumber(self):
        w = _ConcreteWriter('out.avi')
        self._feed(w, 5)
        self.assertEqual(w.framenumber, 5)

    def test_write_at_target_emits_finished(self):
        w = _ConcreteWriter('out.avi', nframes=2)
        self._feed(w, 2)
        spy = QtTest.QSignalSpy(w.finished)
        w.write(_FRAME)   # at target → finished
        self.assertEqual(len(spy), 1)

    def test_write_at_target_does_not_write_frame(self):
        w = _ConcreteWriter('out.avi', nframes=1)
        self._feed(w, 1)
        w.write(_FRAME)   # at target → finished, no write
        self.assertEqual(len(w._written), 1)

    def test_nskip_one_writes_every_frame(self):
        w = _ConcreteWriter('out.avi', nskip=1)
        self.assertEqual(self._feed(w, 5), [0, 1, 2, 3, 4])

    def test_nskip_two_writes_every_second_frame(self):
        w = _ConcreteWriter('out.avi', nskip=2)
        self.assertEqual(self._feed(w, 7), [0, 2, 4, 6])

    def test_nskip_three_writes_every_third_frame(self):
        w = _ConcreteWriter('out.avi', nskip=3)
        self.assertEqual(self._feed(w, 10), [0, 3, 6, 9])

    def test_framenumber_counts_frames_seen(self):
        w = _ConcreteWriter('out.avi', nskip=3)
        self._feed(w, 10)
        self.assertEqual(w.framenumber, 10)

    def test_frame_number_signal_counts_frames_written(self):
        w = _ConcreteWriter('out.avi', nskip=2)
        spy = QtTest.QSignalSpy(w.frameNumber)
        self._feed(w, 6)
        self.assertEqual([args[0] for args in spy], [1, 2, 3])

    def test_nframes_counts_frames_written_with_nskip(self):
        w = _ConcreteWriter('out.avi', nframes=2, nskip=3)
        spy = QtTest.QSignalSpy(w.finished)
        self.assertEqual(self._feed(w, 20), [0, 3])
        self.assertGreater(len(spy), 0)

    def test_blank_mode_writes_zeros(self):
        w = _ConcreteWriter('out.avi')
        w.blank = True
        w.write(np.ones_like(_FRAME))
        np.testing.assert_array_equal(w._written[0], np.zeros_like(_FRAME))

    def test_non_blank_mode_writes_original_frame(self):
        w = _ConcreteWriter('out.avi')
        frame = np.ones((480, 640), dtype=np.uint8) * 128
        w.write(frame)
        np.testing.assert_array_equal(w._written[0], frame)


class TestQVideoWriterAbstractBodies(unittest.TestCase):
    '''Exercise the abstract-method bodies reachable via super().'''

    def test_super_open_returns_none(self):
        w = _SuperCallingWriter('out.avi')
        result = w.open(_FRAME)
        self.assertIsNone(result)

    def test_super_isopen_returns_false(self):
        w = _SuperCallingWriter('out.avi')
        self.assertFalse(w.isOpen())

    def test_super_write_returns_none(self):
        w = _SuperCallingWriter('out.avi')
        result = w._write(_FRAME, FrameInfo(0, 0.))
        self.assertIsNone(result)

    def test_super_close_returns_none(self):
        w = _SuperCallingWriter('out.avi')
        result = w.close()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
