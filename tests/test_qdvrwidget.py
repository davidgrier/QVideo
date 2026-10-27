'''Unit tests for QDVRWidget.'''
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from unittest.mock import patch, MagicMock
from QVideo.tests.signals import record
from QVideo.lib.videotypes import FrameInfo
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.dvr.QDVRWidget import QDVRWidget, _clock, _h5py_available


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_dialogs = []


def setUpModule():
    '''A dialog that a test did not expect fails it instead of hanging.'''
    for name in ('warning', 'question'):
        patcher = patch.object(
            QtWidgets.QMessageBox, name,
            side_effect=AssertionError(f'unexpected {name} dialog'))
        patcher.start()
        _dialogs.append(patcher)


def tearDownModule():
    for patcher in _dialogs:
        patcher.stop()


class MockSource(QtCore.QObject):
    '''Minimal video source with a real newFrame signal.'''
    newFrame = QtCore.Signal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.fps = 30.

_FRAME = np.zeros((4, 4), dtype=np.uint8)


class MockWriter(QtCore.QObject):
    '''Minimal writer with real Qt signals.'''
    frameNumber = QtCore.Signal(int)
    finished = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.received = None
        self.shutdowns = 0
        self.target = kwargs.get('nframes', 10)
        self.nskip = kwargs.get('nskip', 1)

    def write(self, frame):
        pass

    def close(self):
        pass

    def shutdown(self):
        self.shutdowns += 1

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
        self.seeks = []
        self.source = MagicMock(length=100, fps=30., framenumber=0)

    def seek(self, framenumber):
        self.seeks.append(framenumber)

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
    source.newFrame.connect(widget._watch)
    widget._shutdown.connect(writer.shutdown)
    widget._writer = writer
    widget._thread = thread
    widget._fps = source.fps
    return writer, thread


def setup_playing(widget):
    '''Manually wire playback state as play() would.'''
    player = MockPlayer()
    player.newFrame.connect(widget._follow)
    widget._player = player
    widget._length, widget._fps = 100, 30.
    return player


class FileCase(unittest.TestCase):
    '''A test case with a scratch directory holding ``self.path``.'''

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = self.dir / 'test.avi'

    def widget(self, create=True, **kwargs):
        if create:
            self.path.touch()
        return make_widget(filename=str(self.path), **kwargs)


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

    def test_filename_not_updated_while_recording(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget.filename = 'new.avi'
        self.assertNotEqual(widget.filename, 'new.avi')

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

    def test_setFrameNumber_shows_the_recorded_frames(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget.setFrameNumber(7)
        self.assertEqual(widget.framenumber, 7)
        self.assertIn('7', widget.positionLabel.text())


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
        spy = record(widget.recording)
        mock_thread = MockThread()
        with patch.dict(QDVRWidget.Writer, {'.avi': MockWriter}):
            with patch.object(QtCore, 'QThread', return_value=mock_thread):
                widget.record()
        self.assertEqual(len(spy), 1)
        self.assertTrue(spy[0][0])

    def watching(self, **kwargs):
        '''A recording whose writer has taken up the frame stamped t=10.'''
        widget, source = make_widget_with_source()
        for key, value in kwargs.items():
            setattr(widget, key, value)
        writer, _ = setup_recording(widget, source)
        writer.received = FrameInfo(0, 10.)
        return widget, writer

    def capture(self, widget, t):
        widget._watch(_FRAME, FrameInfo(1, t))

    def test_defaults(self):
        widget = make_widget()
        self.assertTrue(widget.stopWhenBehind)
        self.assertEqual(widget.lagLimit, 1.)
        self.assertIsNone(widget.maxMemory)

    def test_a_writer_keeping_up_is_left_alone(self):
        widget, _ = self.watching()
        self.capture(widget, 10.5)
        self.assertTrue(widget.isRecording())

    def test_falling_behind_stops_the_recording_by_default(self):
        widget, _ = self.watching()
        with self.assertLogs('QVideo.dvr.QDVRWidget', 'ERROR'):
            self.capture(widget, 12.)
        self.assertFalse(widget.isRecording())

    def test_the_reason_is_reported(self):
        widget, _ = self.watching()
        reasons = []
        widget.stopped.connect(reasons.append)
        with self.assertLogs('QVideo.dvr.QDVRWidget', 'ERROR'):
            self.capture(widget, 12.)
        self.assertEqual(len(reasons), 1)
        self.assertIn('2.0 s behind', reasons[0])

    def test_the_reason_says_what_to_try(self):
        widget, _ = self.watching()
        reasons = []
        widget.stopped.connect(reasons.append)
        with self.assertLogs('QVideo.dvr.QDVRWidget', 'ERROR') as logs:
            self.capture(widget, 12.)
        self.assertIn('record to .h5', reasons[0])
        self.assertIn('lower the frame size or rate', reasons[0])
        self.assertIn(reasons[0], logs.output[0])

    def test_a_video_writer_without_pyav_suggests_installing_it(self):
        widget, _ = self.watching()
        module = sys.modules['QVideo.dvr.QDVRWidget']
        with patch.object(module, '_pyav_available', False):
            self.assertIn('install QVideo[av]', widget._remedy())
        with patch.object(module, '_pyav_available', True):
            self.assertNotIn('QVideo[av]', widget._remedy())

    def test_without_h5py_it_says_how_to_record_to_hdf5(self):
        widget, _ = self.watching()
        without = {k: v for k, v in QDVRWidget.Writer.items() if k != '.h5'}
        with patch.object(QDVRWidget, 'Writer', without):
            remedy = widget._remedy()
        self.assertIn('install QVideo[dvr] to record to .h5', remedy)

    def test_an_hdf5_recording_suggests_a_faster_disk(self):
        from QVideo.dvr.QHDF5Writer import QHDF5Writer
        widget, _ = self.watching()
        widget._writer = QHDF5Writer('test.h5', fps=30)
        remedy = widget._remedy()
        self.assertIn('faster disk', remedy)
        self.assertNotIn('record to .h5', remedy)

    def test_behind_is_emitted_before_the_recording_stops(self):
        widget, _ = self.watching()
        states = []
        widget.behind.connect(lambda lag: states.append(widget.isRecording()))
        with self.assertLogs('QVideo.dvr.QDVRWidget', 'ERROR'):
            self.capture(widget, 12.)
        self.assertEqual(states, [True])

    def test_recording_continues_when_stopping_is_disabled(self):
        widget, _ = self.watching(stopWhenBehind=False)
        stops = []
        widget.stopped.connect(stops.append)
        self.capture(widget, 12.)
        self.assertTrue(widget.isRecording())
        self.assertEqual(stops, [])

    def test_staying_behind_is_reported_once(self):
        widget, _ = self.watching(stopWhenBehind=False)
        lags = []
        widget.behind.connect(lags.append)
        for t in (12., 12.1, 12.2):
            self.capture(widget, t)
        self.assertEqual(lags, [2.])

    def test_catching_up_rearms_the_report(self):
        widget, writer = self.watching(stopWhenBehind=False)
        lags = []
        widget.behind.connect(lags.append)
        self.capture(widget, 12.)
        writer.received = FrameInfo(1, 12.)
        self.capture(widget, 12.1)
        self.capture(widget, 14.)
        self.assertEqual(len(lags), 2)

    def test_the_backlog_is_a_fraction_of_the_allowance(self):
        widget, _ = self.watching()
        fractions = []
        widget.backlog.connect(fractions.append)
        self.capture(widget, 10.5)
        self.assertEqual(fractions, [0.5])

    def test_the_backlog_is_reported_in_steps(self):
        widget, _ = self.watching()
        fractions = []
        widget.backlog.connect(fractions.append)
        for t in (10.46, 10.48, 10.5):  # all within one 5% step
            self.capture(widget, t)
        self.assertEqual(len(fractions), 1)
        self.capture(widget, 10.6)
        self.assertEqual(len(fractions), 2)

    def test_a_writer_keeping_up_reports_nothing(self):
        widget, _ = self.watching()
        fractions = []
        widget.backlog.connect(fractions.append)
        self.capture(widget, 10.)
        self.assertEqual(fractions, [])

    def test_a_writer_ahead_of_the_capture_reports_nothing(self):
        widget, _ = self.watching()
        fractions = []
        widget.backlog.connect(fractions.append)
        self.capture(widget, 9.)
        self.assertEqual(fractions, [])

    def test_catching_up_is_reported(self):
        widget, writer = self.watching()
        fractions = []
        widget.backlog.connect(fractions.append)
        self.capture(widget, 10.8)
        writer.received = FrameInfo(1, 10.8)
        self.capture(widget, 10.85)
        self.assertEqual(len(fractions), 2)
        self.assertLess(fractions[1], fractions[0])

    def test_the_backlog_is_reported_before_the_report_of_falling_behind(self):
        widget, _ = self.watching(stopWhenBehind=False)
        events = []
        widget.backlog.connect(lambda f: events.append('backlog'))
        widget.behind.connect(lambda lag: events.append('behind'))
        self.capture(widget, 12.)
        self.assertEqual(events, ['backlog', 'behind'])

    def test_recording_starts_with_no_backlog(self):
        widget, source = make_widget_with_source()
        widget._level = 7
        with patch.dict(QDVRWidget.Writer, {'.avi': MockWriter}), \
                patch.object(QtCore, 'QThread', return_value=MockThread()):
            widget.record()
        self.assertEqual(widget._level, 0)

    def test_the_limit_can_be_changed(self):
        widget, _ = self.watching(lagLimit=5.)
        self.capture(widget, 12.)
        self.assertTrue(widget.isRecording())

    def test_a_small_memory_budget_stops_the_recording(self):
        # 0.5 s of a 30 Hz source of 16-byte frames
        widget, _ = self.watching(_budget=0.5 * 30 * _FRAME.nbytes)
        with self.assertLogs('QVideo.dvr.QDVRWidget', 'ERROR'):
            self.capture(widget, 10.6)
        self.assertFalse(widget.isRecording())

    def test_a_large_memory_budget_leaves_the_time_limit_in_charge(self):
        widget, _ = self.watching(_budget=1e12)
        self.capture(widget, 10.9)
        self.assertTrue(widget.isRecording())
        with self.assertLogs('QVideo.dvr.QDVRWidget', 'ERROR'):
            self.capture(widget, 12.)
        self.assertFalse(widget.isRecording())

    def test_the_budget_defaults_to_most_of_the_available_memory(self):
        widget, source = make_widget_with_source()
        free = SimpleNamespace(available=1000)
        with patch.dict(QDVRWidget.Writer, {'.avi': MockWriter}), \
                patch.object(QtCore, 'QThread', return_value=MockThread()), \
                patch('psutil.virtual_memory', return_value=free):
            widget.record()
        self.assertEqual(widget._budget, 800)

    def test_max_memory_overrides_the_default_budget(self):
        widget, source = make_widget_with_source()
        widget.maxMemory = 123
        with patch.dict(QDVRWidget.Writer, {'.avi': MockWriter}), \
                patch.object(QtCore, 'QThread', return_value=MockThread()):
            widget.record()
        self.assertEqual(widget._budget, 123)

    def test_a_writer_that_has_seen_nothing_is_not_late(self):
        widget, writer = self.watching()
        writer.received = None
        self.capture(widget, 99.)
        self.assertTrue(widget.isRecording())

    def test_a_frame_without_info_is_ignored(self):
        widget, _ = self.watching()
        widget._watch(_FRAME)
        self.assertTrue(widget.isRecording())

    def test_a_late_event_after_stopping_is_harmless(self):
        widget, _ = self.watching()
        widget.stop()
        self.capture(widget, 99.)  # queued before stop, delivered after

    def test_record_when_recording_calls_stop(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        with patch.object(widget, 'stop') as mock_stop:
            widget.record()
        mock_stop.assert_called_once()


class TestQDVRWidgetPlay(FileCase):

    def play(self, widget, cls=MockPlayer):
        with patch.dict(QDVRWidget.Player, {'.avi': cls}):
            widget.play()

    def test_play_does_nothing_while_recording(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget.play()
        self.assertFalse(widget.isPlaying())

    def test_play_rejects_unsupported_extension(self):
        self.path = self.dir / 'test.xyz'
        widget = self.widget()
        with self.assertLogs('QVideo.dvr.QDVRWidget', level='ERROR'):
            widget.play()
        self.assertFalse(widget.isPlaying())

    def test_play_warns_when_the_file_does_not_exist(self):
        widget = self.widget(create=False)
        with patch.object(QtWidgets.QMessageBox, 'warning') as warning:
            self.play(widget)
        warning.assert_called_once()
        self.assertIn('test.avi', warning.call_args.args[2])
        self.assertFalse(widget.isPlaying())

    def test_play_starts_playback(self):
        widget = self.widget()
        self.play(widget)
        self.assertTrue(widget.isPlaying())

    def test_play_shows_the_length_of_the_video(self):
        widget = self.widget()
        self.play(widget)
        self.assertEqual(widget.slider.maximum(), 100)
        self.assertEqual(widget.positionLabel.text(), 'frame 0 / 100')

    def test_play_emits_playing_true(self):
        widget = self.widget()
        spy = record(widget.playing)
        self.play(widget)
        self.assertEqual(len(spy), 1)
        self.assertTrue(spy[0][0])

    def test_play_resumes_if_paused(self):
        widget = self.widget()
        self.play(widget)
        widget._player.pause()
        self.assertTrue(widget.isPaused())
        widget.play()
        self.assertFalse(widget.isPaused())

    def test_play_restarts_a_video_that_has_ended(self):
        widget = self.widget()
        self.play(widget)
        widget._display(100, 100, 30.)
        widget._player.pause()
        widget.play()
        self.assertEqual(widget._player.seeks, [0])
        self.assertFalse(widget.isPaused())

    def test_play_does_nothing_if_already_playing(self):
        widget = self.widget()
        self.play(widget)
        first_player = widget._player
        widget.play()
        self.assertIs(widget._player, first_player)

    def test_play_does_not_start_if_player_not_open(self):
        widget = self.widget()

        class ClosedPlayer(MockPlayer):
            def isOpen(self):
                return False

        self.play(widget, ClosedPlayer)
        self.assertFalse(widget.isPlaying())


class TestQDVRWidgetRecordingLoad(unittest.TestCase):
    '''Recording must not ask the camera for anything with every frame.'''

    def test_the_frame_rate_is_read_once_per_recording(self):
        source = MockSource()
        reads = []
        type(source).fps = property(lambda self: reads.append(1) or 30.)
        self.addCleanup(delattr, type(source), 'fps')
        widget = make_widget(source=source)
        with patch.dict(QDVRWidget.Writer, {'.avi': MockWriter}), \
                patch.object(QtCore, 'QThread', return_value=MockThread()):
            widget.record()
        reads.clear()
        for n in range(1, 20):
            source.newFrame.emit(_FRAME)
            widget.setFrameNumber(n)
            widget._watch(_FRAME, FrameInfo(n, 10. + n / 30.))
        self.assertEqual(reads, [])

    def test_a_frame_count_after_the_recording_is_ignored(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget.stop()
        widget.setFrameNumber(5)  # queued before stop, delivered after
        self.assertEqual(widget.framenumber, 0)


class TestQDVRWidgetRecordChecks(FileCase):

    def record(self, widget):
        with patch.dict(QDVRWidget.Writer, {'.avi': MockWriter}), \
                patch.object(QtCore, 'QThread', return_value=MockThread()):
            widget.record()

    def widget(self, create=True):
        widget = super().widget(create)
        widget.source = MockSource()
        return widget

    def test_a_new_file_is_recorded_without_asking(self):
        widget = self.widget(create=False)
        self.record(widget)
        self.assertTrue(widget.isRecording())

    def test_an_existing_file_is_replaced_if_the_user_agrees(self):
        widget = self.widget()
        Yes = QtWidgets.QMessageBox.StandardButton.Yes
        with patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=Yes) as question:
            self.record(widget)
        question.assert_called_once()
        self.assertTrue(widget.isRecording())

    def test_an_existing_file_is_kept_if_the_user_declines(self):
        widget = self.widget()
        No = QtWidgets.QMessageBox.StandardButton.No
        with patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=No):
            self.record(widget)
        self.assertFalse(widget.isRecording())

    def test_the_default_answer_is_to_keep_the_file(self):
        widget = self.widget()
        No = QtWidgets.QMessageBox.StandardButton.No
        with patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=No) as question:
            self.record(widget)
        self.assertEqual(question.call_args.args[-1], No)

    def test_a_read_only_file_is_not_recorded_over(self):
        widget = self.widget()
        with patch('os.access', return_value=False), \
                patch.object(QtWidgets.QMessageBox, 'warning') as warning:
            self.record(widget)
        self.assertIn('read-only', warning.call_args.args[2])
        self.assertFalse(widget.isRecording())

    def test_a_folder_that_cannot_be_written_is_reported(self):
        widget = self.widget(create=False)
        with patch('os.access', return_value=False), \
                patch.object(QtWidgets.QMessageBox, 'warning') as warning:
            self.record(widget)
        self.assertIn(str(self.dir), warning.call_args.args[2])
        self.assertFalse(widget.isRecording())


class TestQDVRWidgetStop(unittest.TestCase):

    def test_stop_when_idle_is_safe(self):
        widget = make_widget()
        widget.stop()

    def test_stop_resets_framenumber(self):
        widget = make_widget()
        widget._display(100, 200, 30.)
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
        spy = record(widget.playing)
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
        spy = record(widget.recording)
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

    def test_stop_shuts_the_writer_down_once(self):
        widget, source = make_widget_with_source()
        writer, _ = setup_recording(widget, source)
        widget.stop()
        self.assertEqual(writer.shutdowns, 1)

    def test_stop_is_safe_when_signals_already_disconnected(self):
        widget, source = make_widget_with_source()
        writer, _ = setup_recording(widget, source)
        source.newFrame.disconnect(writer.write)  # pre-disconnect
        widget.stop()  # must not raise

    def test_stop_waits_until_the_file_is_closed(self):
        widget = make_widget()
        player = setup_playing(widget)
        with patch.object(player, 'wait') as wait:
            widget.stop()
        wait.assert_called_once()

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

    def test_rewind_seeks_to_the_first_frame(self):
        widget = make_widget()
        player = setup_playing(widget)
        widget.rewind()
        self.assertEqual(player.seeks, [0])

    def test_rewind_pauses_playback(self):
        widget = make_widget()
        setup_playing(widget)
        widget.rewind()
        self.assertTrue(widget.isPaused())

    def test_rewind_does_nothing_when_not_playing(self):
        widget = make_widget()
        widget.rewind()  # must not raise


class TestQDVRWidgetSeek(unittest.TestCase):

    def playing(self, at=10):
        widget = make_widget()
        player = setup_playing(widget)
        widget._display(at, 100, 30.)
        return widget, player

    def test_step_forward_shows_the_next_frame(self):
        widget, player = self.playing(at=10)  # showing frame index 9
        widget.step(1)
        self.assertEqual(player.seeks, [10])

    def test_step_back_shows_the_previous_frame(self):
        widget, player = self.playing(at=10)
        widget.step(-1)
        self.assertEqual(player.seeks, [8])

    def test_stepping_pauses(self):
        widget, player = self.playing()
        widget.step(1)
        self.assertTrue(widget.isPaused())

    def test_seek_stays_within_the_video(self):
        widget, player = self.playing()
        widget.seek(-5)
        widget.seek(500)
        self.assertEqual(player.seeks, [0, 99])

    def test_seek_does_not_pause(self):
        widget, player = self.playing()
        widget.seek(20)
        self.assertFalse(widget.isPaused())

    def test_seek_when_not_playing_is_ignored(self):
        make_widget().seek(3)  # must not raise

    def test_moving_the_slider_seeks(self):
        widget, player = self.playing()
        widget.slider.setValue(40)
        self.assertEqual(player.seeks, [39])

    def test_showing_a_frame_does_not_seek(self):
        widget, player = self.playing()
        widget._display(50, 100, 30.)
        self.assertEqual(player.seeks, [])


class TestQDVRWidgetFollow(unittest.TestCase):

    def playing(self, length=100):
        widget = make_widget()
        player = setup_playing(widget)
        widget._length = length
        return widget, player

    def test_the_display_follows_the_reader(self):
        widget, player = self.playing()
        player.source.framenumber = 25
        widget._follow()
        self.assertEqual(widget.framenumber, 25)
        self.assertEqual(widget.positionLabel.text(), 'frame 25 / 100')
        self.assertEqual(widget.timeLabel.text(), '0:00.8 / 0:03.3')

    def test_playback_pauses_at_the_end_of_the_video(self):
        widget, player = self.playing()
        player.source.framenumber = 100
        widget._follow()
        self.assertTrue(widget.isPaused())

    def test_playback_continues_before_the_end(self):
        widget, player = self.playing()
        player.source.framenumber = 99
        widget._follow()
        self.assertFalse(widget.isPaused())

    def test_a_video_of_unknown_length_never_pauses(self):
        widget, player = self.playing(length=0)
        player.source.framenumber = 5
        widget._follow()
        self.assertFalse(widget.isPaused())
        self.assertEqual(widget.slider.maximum(), 5)

    def test_a_late_frame_after_stopping_is_harmless(self):
        widget = make_widget()
        widget._follow()  # queued before stop, delivered after


class TestQDVRWidgetControls(unittest.TestCase):

    def test_idle_without_a_source_only_play_is_available(self):
        widget = make_widget()
        for button in (widget.recordButton, widget.stopButton,
                       widget.rewindButton, widget.backButton,
                       widget.forwardButton):
            self.assertFalse(button.isEnabled())
        self.assertTrue(widget.playButton.isEnabled())

    def test_the_slider_is_drawn_but_inert_when_idle(self):
        slider = make_widget().slider
        Attribute = QtCore.Qt.WidgetAttribute
        self.assertTrue(slider.isEnabled())
        self.assertGreater(slider.maximum(), slider.minimum())
        self.assertTrue(slider.testAttribute(
            Attribute.WA_TransparentForMouseEvents))
        self.assertEqual(slider.focusPolicy(), QtCore.Qt.FocusPolicy.NoFocus)

    def test_the_slider_responds_while_playing(self):
        widget = make_widget()
        setup_playing(widget)
        widget._updateUi()
        self.assertFalse(widget.slider.testAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents))

    def test_the_slider_keeps_a_range_after_stopping(self):
        widget = make_widget()
        setup_playing(widget)
        widget.stop()
        self.assertGreater(widget.slider.maximum(), 0)

    def test_recording_allows_only_stop(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        widget._updateUi()
        self.assertTrue(widget.stopButton.isEnabled())
        self.assertFalse(widget.playButton.isEnabled())

    def test_playing_enables_the_transport_controls(self):
        widget, source = make_widget_with_source()
        setup_playing(widget)
        widget._updateUi()
        for control in (widget.rewindButton, widget.backButton,
                        widget.forwardButton, widget.slider,
                        widget.stopButton):
            self.assertTrue(control.isEnabled())
        self.assertFalse(widget.recordButton.isEnabled())

    def test_the_play_button_shows_pause_while_playing(self):
        widget = make_widget()
        player = setup_playing(widget)
        widget._updateUi()
        self.assertEqual(widget.playButton.toolTip(), 'Pause')
        player.pause()
        widget._updateUi()
        self.assertEqual(widget.playButton.toolTip(), 'Play')

    def test_the_play_button_pauses_then_resumes(self):
        widget = make_widget()
        setup_playing(widget)
        widget.playButton.click()
        self.assertTrue(widget.isPaused())
        widget.playButton.click()
        self.assertFalse(widget.isPaused())

    def test_stopping_restores_the_play_button(self):
        widget = make_widget()
        setup_playing(widget)
        widget._updateUi()
        widget.stop()
        self.assertEqual(widget.playButton.toolTip(), 'Play')

    def test_the_clock(self):
        self.assertEqual(_clock(0), '0:00.0')
        self.assertEqual(_clock(65.4), '1:05.4')


class TestQDVRWidgetFormats(unittest.TestCase):
    '''PyAV records and plays video files if it is installed, else OpenCV.'''

    def names(self, hide_av):
        import os
        import subprocess
        code = (
            'import importlib.util as u\n'
            'real = u.find_spec\n'
            f'hide = {hide_av!r}\n'
            'u.find_spec = lambda n, *a: None if hide and n == "av" '
            'else real(n, *a)\n'
            'from QVideo.dvr.QDVRWidget import QDVRWidget as W\n'
            'print(W.Writer[".mkv"].__name__, W.Player[".avi"].__name__, '
            'W.Writer[".mp4"].__name__)\n')
        result = subprocess.run(
            [sys.executable, '-c', code], capture_output=True, text=True,
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.split()

    def test_pyav_is_preferred_when_it_is_installed(self):
        import importlib.util
        if importlib.util.find_spec('av') is None:
            self.skipTest('PyAV is not installed')
        self.assertEqual(self.names(hide_av=False),
                         ['QPyAVWriter', 'QPyAVSource', 'QPyAVWriter'])

    def test_opencv_is_the_fallback(self):
        self.assertEqual(self.names(hide_av=True),
                         ['QOpenCVWriter', 'QOpenCVSource', 'QOpenCVWriter'])

    def test_hdf5_does_not_depend_on_pyav(self):
        self.assertIn('.h5', QDVRWidget.Writer)


class TestQDVRWidgetIcons(unittest.TestCase):

    def test_the_icons_have_the_color_of_the_button_text(self):
        widget = make_widget()
        text = widget.palette().buttonText().color()
        image = widget.stopButton.icon().pixmap(24, 24).toImage()
        colors = {QtGui.QColor(image.pixel(x, y)).rgb()
                  for x in range(image.width()) for y in range(image.height())
                  if QtGui.QColor.fromRgba(image.pixel(x, y)).alpha() == 255}
        self.assertEqual(colors, {text.rgb()})

    def test_the_icons_follow_a_dark_palette(self):
        widget = make_widget()
        palette = widget.palette()
        palette.setColor(QtGui.QPalette.ColorRole.ButtonText,
                         QtGui.QColor(230, 230, 230))
        widget.setPalette(palette)
        icon = widget._icon(QtWidgets.QStyle.StandardPixmap.SP_MediaStop)
        image = icon.pixmap(24, 24).toImage()
        opaque = [QtGui.QColor.fromRgba(image.pixel(x, y))
                  for x in range(image.width()) for y in range(image.height())
                  if QtGui.QColor.fromRgba(image.pixel(x, y)).alpha() == 255]
        self.assertTrue(opaque)
        self.assertTrue(all(c.red() == 230 for c in opaque))

    def test_the_record_button_has_an_icon(self):
        self.assertEqual(make_widget().recordButton.text(), '')

    def test_the_record_button_falls_back_to_text_without_svg_support(self):
        module = sys.modules['QVideo.dvr.QDVRWidget']
        with patch.object(module, '_record', return_value=QtGui.QIcon()):
            widget = make_widget()
        self.assertEqual(widget.recordButton.text(), 'Record')


class TestQDVRWidgetGetFileName(unittest.TestCase):

    def test_returns_empty_when_playing(self):
        widget = make_widget()
        setup_playing(widget)
        self.assertEqual(widget.getFileName(), '')

    def test_returns_empty_when_recording(self):
        widget, source = make_widget_with_source()
        setup_recording(widget, source)
        self.assertEqual(widget.getFileName(), '')

    def choose(self, widget, *names):
        '''Run getFileName with a dialog that selects *names*.'''
        dialogs = []

        def exec_(dialog):
            dialogs.append(dialog)
            return bool(names)

        with patch.object(QtWidgets.QFileDialog, 'exec', exec_), \
                patch.object(QtWidgets.QFileDialog, 'selectedFiles',
                             return_value=list(names)):
            return widget.getFileName(), dialogs[0]

    def test_the_dialog_selects_and_does_not_save(self):
        _, dialog = self.choose(make_widget(), 'a.avi')
        Dialog = QtWidgets.QFileDialog
        self.assertEqual(dialog.labelText(Dialog.DialogLabel.Accept),
                         'Select')
        self.assertEqual(dialog.acceptMode(), Dialog.AcceptMode.AcceptSave)

    def test_does_not_ask_before_replacing_a_file(self):
        _, dialog = self.choose(make_widget(), 'a.avi')
        Option = QtWidgets.QFileDialog.Option
        self.assertTrue(dialog.testOption(Option.DontConfirmOverwrite))

    def test_sets_the_filename(self):
        widget = make_widget()
        result, _ = self.choose(widget, 'chosen.avi')
        self.assertEqual(result, 'chosen.avi')
        self.assertEqual(widget.filename, 'chosen.avi')

    def test_keeps_the_filename_when_cancelled(self):
        widget = make_widget(filename='original.avi')
        result, _ = self.choose(widget)
        self.assertEqual(result, '')
        self.assertEqual(widget.filename, 'original.avi')


class TestQDVRWidgetNoFilename(unittest.TestCase):

    def test_record_does_nothing_without_filename(self):
        widget, source = make_widget_with_source()
        widget.fileEdit.setText('')
        with patch.object(widget, 'getFileName', return_value=''):
            widget.record()
        self.assertFalse(widget.isRecording())

    def test_play_does_nothing_without_filename(self):
        widget = make_widget()
        widget.fileEdit.setText('')
        with patch.object(widget, 'getFileName', return_value=''):
            widget.play()
        self.assertFalse(widget.isPlaying())


class TestQDVRWidgetBuildFilter(unittest.TestCase):

    def test_known_extensions_appear_in_filter(self):
        f = QDVRWidget._buildFilter(save=True)
        self.assertIn('.avi', f)
        if _h5py_available:
            self.assertIn('.h5', f)
        else:
            self.assertNotIn('.h5', f)

    def test_lossless_extensions_grouped_under_lossless_label(self):
        f = QDVRWidget._buildFilter(save=True)
        self.assertIn('Lossless Video', f)
        lossless_group = next(p for p in f.split(';;') if 'Lossless' in p)
        self.assertIn('.avi', lossless_group)
        self.assertIn('.mkv', lossless_group)

    def test_mp4_grouped_under_video_label(self):
        f = QDVRWidget._buildFilter(save=True)
        video_group = next(p for p in f.split(';;') if p.startswith('Video'))
        self.assertIn('.mp4', video_group)
        self.assertNotIn('.avi', video_group)
        self.assertNotIn('.mkv', video_group)

    def test_lossless_group_precedes_video_group(self):
        f = QDVRWidget._buildFilter(save=True)
        self.assertLess(f.index('Lossless'), f.index('Video ('))

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
