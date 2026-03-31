'''Unit tests for QVideoWriter.'''
import unittest
import numpy as np
from qtpy import QtWidgets, QtTest
from QVideo.lib.QVideoWriter import QVideoWriter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640), dtype=np.uint8)


class _ConcreteWriter(QVideoWriter):
    '''Minimal concrete subclass for testing the base-class write() slot.'''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._open = False
        self._written = []

    def open(self, frame):
        self._open = True
        return True

    def isOpen(self):
        return self._open

    def _write(self, frame):
        self._written.append(frame.copy())

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

    def _write(self, frame):
        return super()._write(frame)

    def close(self):
        return super().close()


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

    def test_write_does_not_write_on_open_call(self):
        w = _ConcreteWriter('out.avi')
        w.write(_FRAME)   # triggers open(), then returns
        self.assertEqual(len(w._written), 0)

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
    '''Tests for writing once the file is open.'''

    def _opened(self, **kwargs):
        w = _ConcreteWriter('out.avi', **kwargs)
        w.write(_FRAME)   # opens
        return w

    def test_second_write_calls_internal_write(self):
        w = self._opened()
        w.write(_FRAME)
        self.assertEqual(len(w._written), 1)

    def test_write_increments_framenumber(self):
        w = self._opened()
        w.write(_FRAME)
        self.assertEqual(w.framenumber, 1)

    def test_write_emits_frame_number(self):
        w = self._opened()
        spy = QtTest.QSignalSpy(w.frameNumber)
        w.write(_FRAME)
        self.assertEqual(len(spy), 1)
        self.assertEqual(spy[0][0], 1)

    def test_multiple_writes_accumulate_framenumber(self):
        w = self._opened()
        for _ in range(5):
            w.write(_FRAME)
        self.assertEqual(w.framenumber, 5)

    def test_write_at_target_emits_finished(self):
        w = _ConcreteWriter('out.avi', nframes=2)
        w.write(_FRAME)   # opens
        w.write(_FRAME)   # writes frame → framenumber = 1
        w.write(_FRAME)   # writes frame → framenumber = 2
        spy = QtTest.QSignalSpy(w.finished)
        w.write(_FRAME)   # framenumber >= target → finished
        self.assertEqual(len(spy), 1)

    def test_write_at_target_does_not_write_frame(self):
        w = _ConcreteWriter('out.avi', nframes=1)
        w.write(_FRAME)   # opens
        w.write(_FRAME)   # writes → framenumber = 1 = target
        count_before = len(w._written)
        w.write(_FRAME)   # at target → finished, no write
        self.assertEqual(len(w._written), count_before)

    def test_write_skips_frame_when_nskip_not_met(self):
        w = _ConcreteWriter('out.avi', nskip=2)
        w.write(_FRAME)   # opens
        w.write(_FRAME)   # framenumber=0, 0%2==0 → writes
        w.write(_FRAME)   # framenumber=1, 1%2!=0 → skips
        self.assertEqual(len(w._written), 1)

    def test_blank_mode_writes_zeros(self):
        w = self._opened()
        w.blank = True
        w.write(_FRAME)
        np.testing.assert_array_equal(w._written[0], np.zeros_like(_FRAME))

    def test_non_blank_mode_writes_original_frame(self):
        w = self._opened()
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
        result = w._write(_FRAME)
        self.assertIsNone(result)

    def test_super_close_returns_none(self):
        w = _SuperCallingWriter('out.avi')
        result = w.close()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
