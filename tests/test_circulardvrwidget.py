'''Unit tests for dvr.QCircularDVRWidget.'''
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
from qtpy import QtWidgets, QtCore

from QVideo.dvr.QCircularBuffer import QCircularBuffer
from QVideo.dvr.QCircularDVRWidget import QCircularDVRWidget
from QVideo.dvr.QDVRWidget import QDVRWidget
from QVideo.lib.videotypes import FrameInfo


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_source(fps=30.):
    source = MagicMock()
    source.fps = fps
    source.newFrame = MagicMock()
    source.newFrame.connect = MagicMock()
    source.newFrame.disconnect = MagicMock()
    return source


class TestConstruction(unittest.TestCase):

    def test_creates_successfully(self):
        widget = QCircularDVRWidget()
        self.assertIsInstance(widget, QCircularDVRWidget)

    def test_is_qwidget(self):
        widget = QCircularDVRWidget()
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_has_buffer(self):
        widget = QCircularDVRWidget()
        self.assertIsInstance(widget.buffer, QCircularBuffer)

    def test_save_button_disabled_without_source(self):
        widget = QCircularDVRWidget()
        self.assertFalse(widget._saveButton.isEnabled())

    def test_source_is_none_initially(self):
        widget = QCircularDVRWidget()
        self.assertIsNone(widget.source)

    def test_construction_with_source(self):
        source = make_source()
        widget = QCircularDVRWidget(source)
        self.assertIs(widget.source, source)


class TestSourceProperty(unittest.TestCase):

    def test_set_source_enables_save_button(self):
        widget = QCircularDVRWidget()
        widget.source = make_source()
        self.assertTrue(widget._saveButton.isEnabled())

    def test_set_source_connects_newframe(self):
        widget = QCircularDVRWidget()
        source = make_source()
        widget.source = source
        source.newFrame.connect.assert_called_with(widget._buffer.append)

    def test_set_source_uses_source_fps(self):
        widget = QCircularDVRWidget()
        source = make_source(fps=60.)
        widget.source = source
        self.assertEqual(widget._buffer.fps, 60.)

    def test_replace_source_disconnects_old(self):
        widget = QCircularDVRWidget()
        source1 = make_source()
        source2 = make_source()
        widget.source = source1
        widget.source = source2
        source1.newFrame.disconnect.assert_called_with(widget._buffer.append)

    def test_set_source_none_disables_save_button(self):
        widget = QCircularDVRWidget()
        source = make_source()
        widget.source = source
        widget.source = None
        self.assertFalse(widget._saveButton.isEnabled())

    def test_set_source_none_disconnects(self):
        widget = QCircularDVRWidget()
        source = make_source()
        widget.source = source
        widget.source = None
        source.newFrame.disconnect.assert_called_with(widget._buffer.append)

    def test_source_without_fps_skips_fps_assignment(self):
        widget = QCircularDVRWidget()
        source = make_source(fps=0.)
        widget.source = source
        self.assertEqual(widget._buffer.fps, 24.)  # unchanged default


class TestDurationSpinbox(unittest.TestCase):

    def test_duration_spinbox_changes_buffer_duration(self):
        widget = QCircularDVRWidget()
        widget._durationBox.setValue(10)
        self.assertEqual(widget._buffer.duration, 10)


class TestSavedSignal(unittest.TestCase):

    def test_saved_signal_emitted_on_success(self):
        widget = QCircularDVRWidget()
        widget.source = make_source()
        widget._fileEdit.setText('/tmp/circular_test.mkv')
        spy = []
        widget.saved.connect(spy.append)
        widget._write = MagicMock(return_value=True)
        widget._save()
        self.assertEqual(spy, ['/tmp/circular_test.mkv'])

    def test_saved_signal_not_emitted_on_failure(self):
        widget = QCircularDVRWidget()
        widget.source = make_source()
        widget._fileEdit.setText('/tmp/circular_test.mkv')
        spy = []
        widget.saved.connect(spy.append)
        widget._write = MagicMock(return_value=False)
        widget._save()
        self.assertEqual(spy, [])

    def test_save_button_reenabled_after_save(self):
        widget = QCircularDVRWidget()
        widget.source = make_source()
        widget._fileEdit.setText('/tmp/circular_test.mkv')
        widget._write = MagicMock(return_value=True)
        widget._save()
        self.assertTrue(widget._saveButton.isEnabled())


class TestBufferProperty(unittest.TestCase):

    def test_buffer_property_returns_circular_buffer(self):
        widget = QCircularDVRWidget()
        self.assertIsInstance(widget.buffer, QCircularBuffer)

    def test_buffer_is_same_object(self):
        widget = QCircularDVRWidget()
        self.assertIs(widget.buffer, widget._buffer)


class TestFileSelection(unittest.TestCase):

    def dialog(self, filename):
        return patch.object(QtWidgets.QFileDialog, 'getSaveFileName',
                            return_value=(filename, ''))

    def test_browsing_sets_the_file_name(self):
        widget = QCircularDVRWidget()
        with self.dialog('/data/run.mkv'):
            widget._browse()
        self.assertEqual(widget._fileEdit.text(), '/data/run.mkv')

    def test_cancelling_keeps_the_file_name(self):
        widget = QCircularDVRWidget()
        widget._fileEdit.setText('/data/old.mkv')
        with self.dialog(''):
            widget._browse()
        self.assertEqual(widget._fileEdit.text(), '/data/old.mkv')

    def test_saving_without_a_name_asks_for_one(self):
        widget = QCircularDVRWidget()
        widget._fileEdit.setText('')
        with self.dialog('/data/run.mkv'), \
                patch.object(widget, '_write', return_value=True) as write:
            widget._save()
        write.assert_called_once_with('/data/run.mkv')

    def test_saving_does_nothing_if_no_name_is_given(self):
        widget = QCircularDVRWidget()
        widget._fileEdit.setText('')
        with self.dialog(''), \
                patch.object(widget, '_write') as write:
            widget._save()
        write.assert_not_called()


class FakeWriter(QtCore.QObject):
    '''Records what it is asked to write.'''

    finished = QtCore.Signal()
    made = []
    fail_after = None

    def __init__(self, filename, fps=24., nframes=10, **kwargs):
        super().__init__()
        self.filename, self.fps, self.nframes = filename, fps, nframes
        self.written = []
        self.closed = False
        type(self).made.append(self)

    def write(self, frame, info=None):
        self.written.append((frame, info))
        if len(self.written) == self.fail_after:
            self.finished.emit()

    def close(self):
        self.closed = True


class TestWrite(unittest.TestCase):
    '''The widget writes the buffer with the DVR's writer for the extension.'''

    def setUp(self):
        FakeWriter.made = []
        FakeWriter.fail_after = None
        patcher = patch.dict(QDVRWidget.Writer, {'.fake': FakeWriter})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.widget = QCircularDVRWidget()
        for i in range(4):
            self.widget.buffer.append(np.full((2, 2), i, np.uint8),
                                      FrameInfo(i, 10. + 0.5 * i))

    def test_the_frames_go_to_the_writer_in_order_with_their_information(self):
        self.assertTrue(self.widget._write('run.fake'))
        writer, = FakeWriter.made
        self.assertEqual([info.index for _, info in writer.written],
                         [0, 1, 2, 3])
        self.assertEqual([int(f[0, 0]) for f, _ in writer.written],
                         [0, 1, 2, 3])

    def test_the_writer_is_told_the_rate_and_the_number_of_frames(self):
        self.widget._write('run.fake')
        writer, = FakeWriter.made
        self.assertEqual(writer.filename, 'run.fake')
        self.assertAlmostEqual(writer.fps, 2.0)  # 3 intervals in 1.5 s
        self.assertEqual(writer.nframes, 4)

    def test_the_writer_is_closed(self):
        self.widget._write('run.fake')
        self.assertTrue(FakeWriter.made[0].closed)

    def test_an_empty_buffer_writes_nothing(self):
        self.widget.buffer.clear()
        self.assertFalse(self.widget._write('run.fake'))
        self.assertEqual(FakeWriter.made, [])

    def test_an_unsupported_extension_is_reported(self):
        with self.assertLogs('QVideo.dvr.QCircularDVRWidget', 'ERROR'):
            self.assertFalse(self.widget._write('run.xyz'))

    def test_a_writer_that_gives_up_stops_the_save(self):
        FakeWriter.fail_after = 2
        self.assertFalse(self.widget._write('run.fake'))
        writer, = FakeWriter.made
        self.assertEqual(len(writer.written), 2)
        self.assertTrue(writer.closed)

    def test_a_file_that_cannot_be_created_gives_up_at_once(self):
        FakeWriter.fail_after = 1
        self.assertFalse(self.widget._write('run.fake'))
        self.assertEqual(len(FakeWriter.made[0].written), 1)


class TestRoundTrip(unittest.TestCase):
    '''What the buffer holds is what the file holds.'''

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.widget = QCircularDVRWidget()
        rng = np.random.default_rng(0)
        self.frames = [rng.integers(0, 256, (24, 32), dtype=np.uint8)
                       for _ in range(5)]
        for i, frame in enumerate(self.frames):
            self.widget.buffer.append(frame, FrameInfo(i, 10. + i / 30.))

    def read_back(self, suffix):
        path = str(self.dir / f'buffer{suffix}')
        self.assertTrue(self.widget._write(path))
        reader = QDVRWidget.Player[suffix](path).source
        self.addCleanup(reader.close)
        frames = [reader.read()[1] for _ in self.frames]
        return [f if f.ndim == 2 else f[..., 0] for f in frames]

    def check(self, suffix):
        for sent, got in zip(self.frames, self.read_back(suffix)):
            np.testing.assert_array_equal(sent, got)

    def test_a_video_file_returns_every_pixel(self):
        for suffix in ('.mkv', '.avi'):
            with self.subTest(suffix):
                self.check(suffix)

    def test_the_opencv_writers_return_every_pixel_too(self):
        from QVideo.dvr.QOpenCVWriter import QOpenCVWriter
        from QVideo.dvr.QOpenCVReader import QOpenCVSource
        with patch.dict(QDVRWidget.Writer, {'.mkv': QOpenCVWriter}), \
                patch.dict(QDVRWidget.Player, {'.mkv': QOpenCVSource}):
            self.check('.mkv')

    def test_an_hdf5_file_returns_every_pixel(self):
        if '.h5' not in QDVRWidget.Writer:
            self.skipTest('h5py is not installed')
        self.check('.h5')


if __name__ == '__main__':
    unittest.main()
