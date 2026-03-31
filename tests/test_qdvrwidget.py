'''Unit tests for QDVRWidget.'''
import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from qtpy import QtCore, QtGui, QtWidgets, QtTest
from QVideo.dvr.QDVRWidget import QDVRWidget


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class MockSource(QtCore.QObject):
    '''Minimal video source with a real newFrame signal.'''
    newFrame = QtCore.Signal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.fps = 30.


class MockWriter(QtCore.QObject):
    '''Minimal writer with real Qt signals.'''
    frameNumber = QtCore.Signal(int)
    finished = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__()

    def write(self, frame):
        pass

    def close(self):
        pass

    def moveToThread(self, thread):
        pass


class MockThread(QtCore.QObject):
    '''Stand-in for QThread without actually spawning a thread.'''
    finished = QtCore.Signal()

    def start(self):
        pass

    def quit(self):
        pass

    def wait(self):
        pass


class MockPlayer(QtCore.QThread):
    '''Minimal player/source with real Qt signals.'''
    newFrame = QtCore.Signal(np.ndarray)

    def __init__(self, filename=None):
        super().__init__()
        self._open = True
        self._paused = False
        self.source = MagicMock()

    def isOpen(self):
        return self._open

    def start(self):
        pass

    def stop(self):
        pass

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def isPaused(self):
        return self._paused


def make_widget(source=None, filename='test.avi'):
    return QDVRWidget(source=source, filename=filename)


def make_widget_with_source():
    source = MockSource()
    widget = make_widget(source=source)
    return widget, source


def setup_recording(widget, source):
    '''Manually wire recording state as record() would, without threads.'''
    writer = MockWriter()
    thread = MockThread()
    source.newFrame.connect(writer.write)
    writer.frameNumber.connect(widget.setFrameNumber)
    writer.finished.connect(widget.stop)
    thread.finished.connect(writer.close)
    widget._writer = writer
    widget._thread = thread
    return writer, thread


def setup_playing(widget):
    '''Manually wire playback state as play() would.'''
    player = MockPlayer()
    player.newFrame.connect(widget.stepFrameNumber)
    widget._player = player
    return player


class TestQDVRWidgetInit(unittest.TestCase):

    def test_not_recording_initially(self):
        widget = make_widget()
        self.assertFalse(widget.isRecording())

    def test_not_playing_initially(self):
        widget = make_widget()
        self.assertFalse(widget.isPlaying())

    def test_not_paused_initially(self):
        widget = make_widget()
        self.assertFalse(widget.isPaused())

    def test_source_none_by_default(self):
        widget = make_widget()
        self.assertIsNone(widget.source)

    def test_record_button_disabled_without_source(self):
        widget = make_widget()
        self.assertFalse(widget.recordButton.isEnabled())

    def test_record_button_enabled_with_source(self):
        widget, _ = make_widget_with_source()
        self.assertTrue(widget.recordButton.isEnabled())

    def test_framenumber_zero_initially(self):
        widget = make_widget()
        self.assertEqual(widget.framenumber, 0)


class TestQDVRWidgetProperties(unittest.TestCase):

    def test_filename_setter_getter(self):
        widget = make_widget()
        widget.filename = 'output.avi'
        self.assertEqual(widget.filename, 'output.avi')

    def test_playname_setter_getter(self):
        widget = make_widget()
        widget.playname = 'input.avi'
        self.assertEqual(widget.playname, 'input.avi')

    def test_filename_not_updated_while_recording(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget.filename = 'new.avi'
        self.assertNotEqual(widget.filename, 'new.avi')

    def test_playname_not_updated_while_playing(self):
        widget = make_widget()
        setup_playing(widget)
        widget.playname = 'new.avi'
        self.assertNotEqual(widget.playname, 'new.avi')

    def test_source_setter_stores_source(self):
        widget, source = make_widget_with_source()
        self.assertIs(widget.source, source)

    def test_source_setter_disables_record_button_on_none(self):
        widget, _ = make_widget_with_source()
        widget.source = None
        self.assertFalse(widget.recordButton.isEnabled())

    def test_filename_setter_ignores_none(self):
        widget = make_widget(filename='original.avi')
        widget.filename = None
        self.assertEqual(widget.filename, 'original.avi')

    def test_framenumber_setter(self):
        widget = make_widget()
        widget.framenumber = 42
        self.assertEqual(widget.framenumber, 42)

    def test_setFrameNumber(self):
        widget = make_widget()
        widget.setFrameNumber(7)
        self.assertEqual(widget.framenumber, 7)

    def test_stepFrameNumber(self):
        widget = make_widget()
        widget.framenumber = 5
        widget.stepFrameNumber()
        self.assertEqual(widget.framenumber, 6)


class TestQDVRWidgetRecord(unittest.TestCase):

    def test_record_does_nothing_without_source(self):
        widget = make_widget()
        widget.record()
        self.assertFalse(widget.isRecording())

    def test_record_does_nothing_while_playing(self):
        widget, source = make_widget_with_source()
        setup_playing(widget)
        widget.record()
        self.assertFalse(widget.isRecording())

    def test_record_rejects_unsupported_extension(self):
        widget, _ = make_widget_with_source()
        widget.filename = 'test.xyz'
        with self.assertLogs('QVideo.dvr.QDVRWidget', level='ERROR'):
            widget.record()
        self.assertFalse(widget.isRecording())

    def test_record_starts_recording(self):
        widget, source = make_widget_with_source()
        mock_thread = MockThread()
        with patch.dict(QDVRWidget.Writer, {'.avi': MockWriter}):
            with patch.object(QtCore, 'QThread', return_value=mock_thread):
                widget.record()
        self.assertTrue(widget.isRecording())

    def test_record_emits_recording_true(self):
        widget, source = make_widget_with_source()
        spy = QtTest.QSignalSpy(widget.recording)
        mock_thread = MockThread()
        with patch.dict(QDVRWidget.Writer, {'.avi': MockWriter}):
            with patch.object(QtCore, 'QThread', return_value=mock_thread):
                widget.record()
        self.assertEqual(len(spy), 1)
        self.assertTrue(spy[0][0])

    def test_record_when_recording_calls_stop(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        with patch.object(widget, 'stop') as mock_stop:
            widget.record()
        mock_stop.assert_called_once()


class TestQDVRWidgetPlay(unittest.TestCase):

    def test_play_does_nothing_while_recording(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget.play()
        self.assertFalse(widget.isPlaying())

    def test_play_rejects_unsupported_extension(self):
        widget = make_widget()
        widget.playname = 'test.xyz'
        with self.assertLogs('QVideo.dvr.QDVRWidget', level='ERROR'):
            widget.play()
        self.assertFalse(widget.isPlaying())

    def test_play_starts_playback(self):
        widget = make_widget()
        widget.playname = 'test.avi'
        with patch.dict(QDVRWidget.Player, {'.avi': MockPlayer}):
            widget.play()
        self.assertTrue(widget.isPlaying())

    def test_play_emits_playing_true(self):
        widget = make_widget()
        widget.playname = 'test.avi'
        spy = QtTest.QSignalSpy(widget.playing)
        with patch.dict(QDVRWidget.Player, {'.avi': MockPlayer}):
            widget.play()
        self.assertEqual(len(spy), 1)
        self.assertTrue(spy[0][0])

    def test_play_resumes_if_paused(self):
        widget = make_widget()
        widget.playname = 'test.avi'
        with patch.dict(QDVRWidget.Player, {'.avi': MockPlayer}):
            widget.play()
        widget._player.pause()
        self.assertTrue(widget.isPaused())
        widget.play()
        self.assertFalse(widget.isPaused())

    def test_play_does_nothing_if_already_playing(self):
        widget = make_widget()
        widget.playname = 'test.avi'
        with patch.dict(QDVRWidget.Player, {'.avi': MockPlayer}):
            widget.play()
        first_player = widget._player
        widget.play()
        self.assertIs(widget._player, first_player)

    def test_play_does_not_start_if_player_not_open(self):
        widget = make_widget()
        widget.playname = 'test.avi'

        class ClosedPlayer(MockPlayer):
            def isOpen(self):
                return False

        with patch.dict(QDVRWidget.Player, {'.avi': ClosedPlayer}):
            widget.play()
        self.assertFalse(widget.isPlaying())


class TestQDVRWidgetStop(unittest.TestCase):

    def test_stop_when_idle_is_safe(self):
        widget = make_widget()
        widget.stop()

    def test_stop_resets_framenumber(self):
        widget = make_widget()
        widget.framenumber = 100
        widget.stop()
        self.assertEqual(widget.framenumber, 0)

    def test_stop_stops_playback(self):
        widget = make_widget()
        setup_playing(widget)
        widget.stop()
        self.assertFalse(widget.isPlaying())

    def test_stop_emits_playing_false(self):
        widget = make_widget()
        setup_playing(widget)
        spy = QtTest.QSignalSpy(widget.playing)
        widget.stop()
        self.assertEqual(len(spy), 1)
        self.assertFalse(spy[0][0])

    def test_stop_stops_recording(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget.stop()
        self.assertFalse(widget.isRecording())

    def test_stop_emits_recording_false(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        spy = QtTest.QSignalSpy(widget.recording)
        widget.stop()
        self.assertEqual(len(spy), 1)
        self.assertFalse(spy[0][0])

    def test_stop_clears_thread(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget.stop()
        self.assertIsNone(widget._thread)

    def test_stop_clears_writer(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget.stop()
        self.assertIsNone(widget._writer)

    def test_stop_calls_writer_close(self):
        widget, source = make_widget_with_source()
        writer, _ = setup_recording(widget, source)
        with patch.object(writer, 'close') as mock_close:
            widget.stop()
        mock_close.assert_called_once()

    def test_stop_is_safe_when_signals_already_disconnected(self):
        widget, source = make_widget_with_source()
        writer, _ = setup_recording(widget, source)
        source.newFrame.disconnect(writer.write)  # pre-disconnect
        widget.stop()  # must not raise

    def test_stop_clears_player(self):
        widget = make_widget()
        setup_playing(widget)
        widget.stop()
        self.assertIsNone(widget._player)


class TestQDVRWidgetPause(unittest.TestCase):

    def test_pause_pauses_playback(self):
        widget = make_widget()
        setup_playing(widget)
        widget.pause()
        self.assertTrue(widget.isPaused())

    def test_pause_resumes_if_already_paused(self):
        widget = make_widget()
        setup_playing(widget)
        widget._player.pause()
        widget.pause()
        self.assertFalse(widget.isPaused())

    def test_pause_does_nothing_when_not_playing(self):
        widget = make_widget()
        widget.pause()  # must not raise


class TestQDVRWidgetRewind(unittest.TestCase):

    def test_rewind_calls_source_rewind(self):
        widget = make_widget()
        setup_playing(widget)
        widget.rewind()
        widget._player.source.rewind.assert_called_once()

    def test_rewind_resets_framenumber(self):
        widget = make_widget()
        setup_playing(widget)
        widget.framenumber = 5
        widget.rewind()
        self.assertEqual(widget.framenumber, 0)

    def test_rewind_pauses_playback(self):
        widget = make_widget()
        setup_playing(widget)
        widget.rewind()
        self.assertTrue(widget.isPaused())

    def test_rewind_does_nothing_when_not_playing(self):
        widget = make_widget()
        widget.rewind()  # must not raise


class TestQDVRWidgetGetFileName(unittest.TestCase):

    def test_returns_empty_when_playing(self):
        widget = make_widget()
        setup_playing(widget)
        self.assertEqual(widget.getFileName(save=False), '')

    def test_returns_empty_when_recording(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        self.assertEqual(widget.getFileName(save=True), '')

    def test_calls_open_dialog_when_not_saving(self):
        widget = make_widget()
        mock_dialog = MagicMock(return_value=('', ''))
        with patch.dict(QDVRWidget.GetFileName, {False: mock_dialog}):
            widget.getFileName(save=False)
        mock_dialog.assert_called_once()

    def test_calls_save_dialog_when_saving(self):
        widget = make_widget()
        mock_dialog = MagicMock(return_value=('', ''))
        with patch.dict(QDVRWidget.GetFileName, {True: mock_dialog}):
            widget.getFileName(save=True)
        mock_dialog.assert_called_once()

    def test_updates_playname_when_filename_returned(self):
        widget = make_widget()
        with patch.dict(QDVRWidget.GetFileName,
                        {False: MagicMock(return_value=('chosen.avi', ''))}):
            widget.getFileName(save=False)
        self.assertEqual(widget.playname, 'chosen.avi')

    def test_updates_filename_when_saving(self):
        widget = make_widget()
        with patch.dict(QDVRWidget.GetFileName,
                        {True: MagicMock(return_value=('output.avi', ''))}):
            widget.getFileName(save=True)
        self.assertEqual(widget.filename, 'output.avi')

    def test_does_not_update_filename_when_opening(self):
        widget = make_widget(filename='original.avi')
        with patch.dict(QDVRWidget.GetFileName,
                        {False: MagicMock(return_value=('other.avi', ''))}):
            widget.getFileName(save=False)
        self.assertEqual(widget.filename, 'original.avi')

    def test_save_dialog_updates_playname(self):
        widget = make_widget()
        with patch.dict(QDVRWidget.GetFileName,
                        {True: MagicMock(return_value=('save.avi', ''))}):
            widget.getFileName(save=True)
        self.assertEqual(widget.playname, 'save.avi')

    def test_returns_empty_when_dialog_cancelled(self):
        widget = make_widget()
        with patch.dict(QDVRWidget.GetFileName,
                        {False: MagicMock(return_value=('', ''))}):
            result = widget.getFileName(save=False)
        self.assertEqual(result, '')


class TestQDVRWidgetRecordNoFilename(unittest.TestCase):

    def test_record_does_nothing_without_filename(self):
        widget, source = make_widget_with_source()
        widget.saveEdit.setText('')
        with patch.object(widget, 'getFileName', return_value=''):
            widget.record()
        self.assertFalse(widget.isRecording())


class TestQDVRWidgetPlayNoFilename(unittest.TestCase):

    def test_play_does_nothing_without_playname(self):
        widget = make_widget()
        widget.playEdit.setText('')
        with patch.object(widget, 'getFileName', return_value=''):
            widget.play()
        self.assertFalse(widget.isPlaying())


class TestQDVRWidgetBuildFilter(unittest.TestCase):

    def test_known_extensions_appear_in_filter(self):
        f = QDVRWidget._buildFilter(save=True)
        self.assertIn('.avi', f)
        self.assertIn('.h5', f)

    def test_ungrouped_extension_appears_in_other_group(self):
        class SubWidget(QDVRWidget):
            Writer = {'.avi': None, '.webm': None}
            Player = {}
            FileGroups = {'Video files': {'.avi'}}
        f = SubWidget._buildFilter(save=True)
        self.assertIn('Other files', f)
        self.assertIn('.webm', f)

    def test_no_formats_returns_all_files(self):
        class EmptyWidget(QDVRWidget):
            Writer = {}
            Player = {}
        f = EmptyWidget._buildFilter(save=True)
        self.assertEqual(f, 'All files (*)')


class TestQDVRWidgetCloseEvent(unittest.TestCase):

    def test_close_event_calls_stop(self):
        widget = make_widget()
        with patch.object(widget, 'stop') as mock_stop:
            widget.closeEvent(QtGui.QCloseEvent())
        mock_stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
