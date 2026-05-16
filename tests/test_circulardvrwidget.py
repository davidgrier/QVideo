'''Unit tests for dvr.QCircularDVRWidget.'''
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from qtpy import QtWidgets, QtCore

from QVideo.dvr.QCircularBuffer import QCircularBuffer
from QVideo.dvr.QCircularDVRWidget import QCircularDVRWidget


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
        widget._buffer.save = MagicMock(return_value=True)
        widget._save()
        self.assertEqual(spy, ['/tmp/circular_test.mkv'])

    def test_saved_signal_not_emitted_on_failure(self):
        widget = QCircularDVRWidget()
        widget.source = make_source()
        widget._fileEdit.setText('/tmp/circular_test.mkv')
        spy = []
        widget.saved.connect(spy.append)
        widget._buffer.save = MagicMock(return_value=False)
        widget._save()
        self.assertEqual(spy, [])

    def test_save_button_reenabled_after_save(self):
        widget = QCircularDVRWidget()
        widget.source = make_source()
        widget._fileEdit.setText('/tmp/circular_test.mkv')
        widget._buffer.save = MagicMock(return_value=True)
        widget._save()
        self.assertTrue(widget._saveButton.isEnabled())


class TestBufferProperty(unittest.TestCase):

    def test_buffer_property_returns_circular_buffer(self):
        widget = QCircularDVRWidget()
        self.assertIsInstance(widget.buffer, QCircularBuffer)

    def test_buffer_is_same_object(self):
        widget = QCircularDVRWidget()
        self.assertIs(widget.buffer, widget._buffer)


if __name__ == '__main__':
    unittest.main()
