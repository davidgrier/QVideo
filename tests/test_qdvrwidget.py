'''Unit tests for QDVRWidget.'''
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, PropertyMock
import numpy as np
from QVideo.tests import fakes
from QVideo.tests.fakes import FakeWriter, until
from QVideo.tests.signals import record
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.dvr import QPlayer, QRecorder, formats
from QVideo.dvr.QDVRWidget import QDVRWidget, _clock


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


_FRAME = np.zeros((4, 4), dtype=np.uint8)


class MockSource(QtCore.QObject):
    '''Minimal video source with a real newFrame signal.'''
    newFrame = QtCore.Signal(np.ndarray, object)

    def __init__(self):
        super().__init__()
        self.fps = 30.


class FakeReader(fakes.FakeReader):
    LENGTH = 1000


class WidgetCase(unittest.TestCase):
    '''Widgets record to FakeWriter and play FakeReader, and end cleanly.'''

    def setUp(self):
        for table, cls in ((formats.Writer, FakeWriter),
                           (formats.Reader, FakeReader)):
            patcher = patch.dict(table, {'.avi': cls})
            patcher.start()
            self.addCleanup(patcher.stop)

    def make(self, source=None, filename='test.avi'):
        widget = QDVRWidget(source=source, filename=filename)
        self.addCleanup(widget.stop)
        return widget

    def withSource(self):
        source = MockSource()
        return self.make(source=source), source

    def playing(self, length=1000):
        '''A widget that plays a video, paused near its beginning.'''
        widget = self.make()
        with patch.object(FakeReader, 'LENGTH', length):
            widget.playback.start('test.avi')
        widget.pause()
        return widget


class FileCase(WidgetCase):
    '''A test case with a scratch directory holding ``self.path``.'''

    def setUp(self):
        super().setUp()
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = self.dir / 'test.avi'

    def widget(self, create=True, **kwargs):
        if create:
            self.path.touch()
        return self.make(filename=str(self.path), **kwargs)


class TestQDVRWidgetInit(WidgetCase):

    def test_not_recording_initially(self):
        self.assertFalse(self.make().isRecording())

    def test_not_playing_initially(self):
        self.assertFalse(self.make().isPlaying())

    def test_not_paused_initially(self):
        self.assertFalse(self.make().isPaused())

    def test_source_none_by_default(self):
        self.assertIsNone(self.make().source)

    def test_the_widget_holds_a_recorder_and_a_player(self):
        widget = self.make()
        self.assertIsInstance(widget.recorder, QRecorder)
        self.assertIsInstance(widget.playback, QPlayer)

    def test_record_button_disabled_without_source(self):
        self.assertFalse(self.make().recordButton.isEnabled())

    def test_record_button_enabled_with_source(self):
        widget, _ = self.withSource()
        self.assertTrue(widget.recordButton.isEnabled())

    def test_framenumber_zero_initially(self):
        self.assertEqual(self.make().framenumber, 0)

    def test_the_limits_go_to_the_recorder(self):
        widget = QDVRWidget(stopWhenBehind=False, lagLimit=3., maxMemory=9)
        self.addCleanup(widget.stop)
        recorder = widget.recorder
        self.assertIsInstance(recorder, QRecorder)
        self.assertEqual((recorder.stopWhenBehind, recorder.lagLimit,
                          recorder.maxMemory), (False, 3., 9))

    def test_the_defaults_are_those_of_the_recorder(self):
        recorder = self.make().recorder
        self.assertEqual((recorder.stopWhenBehind, recorder.lagLimit,
                          recorder.maxMemory), (True, 1., None))


class TestQDVRWidgetProperties(WidgetCase):

    def test_filename_setter_getter(self):
        widget = self.make()
        widget.filename = 'output.avi'
        self.assertEqual(widget.filename, 'output.avi')

    def test_filename_not_updated_while_recording(self):
        widget, source = self.withSource()
        widget.record()
        widget.filename = 'new.avi'
        self.assertNotEqual(widget.filename, 'new.avi')

    def test_filename_not_updated_while_playing(self):
        widget = self.playing()
        widget.filename = 'new.avi'
        self.assertNotEqual(widget.filename, 'new.avi')

    def test_source_setter_stores_source(self):
        widget, source = self.withSource()
        self.assertIs(widget.source, source)
        self.assertIs(widget.recorder.source, source)

    def test_source_setter_disables_record_button_on_none(self):
        widget, _ = self.withSource()
        widget.source = None
        self.assertFalse(widget.recordButton.isEnabled())

    def test_filename_setter_ignores_none(self):
        widget = self.make(filename='original.avi')
        widget.filename = None
        self.assertEqual(widget.filename, 'original.avi')


class TestQDVRWidgetRecord(WidgetCase):

    def test_record_does_nothing_without_source(self):
        widget = self.make()
        widget.record()
        self.assertFalse(widget.isRecording())

    def test_record_does_nothing_while_playing(self):
        widget, source = self.withSource()
        widget.playback.start('test.avi')
        widget.record()
        self.assertFalse(widget.isRecording())

    def test_record_rejects_unsupported_extension(self):
        widget, _ = self.withSource()
        widget.filename = 'test.xyz'
        with self.assertLogs('QVideo.dvr.QDVRWidget', level='ERROR'):
            widget.record()
        self.assertFalse(widget.isRecording())

    def test_record_starts_recording(self):
        widget, source = self.withSource()
        widget.record()
        self.assertTrue(widget.isRecording())
        self.assertTrue(widget.recorder.isRecording())

    def test_record_emits_recording_true(self):
        widget, source = self.withSource()
        spy = record(widget.recording)
        widget.record()
        self.assertEqual(spy, [(True,)])

    def test_the_recorder_gets_the_duration_and_the_interval(self):
        widget, source = self.withSource()
        widget.nframes.setValue(50)
        widget.nskip.setValue(2)
        widget.record()
        self.assertEqual(widget.recorder.nframes, 50)
        self.assertAlmostEqual(widget.recorder.rate, 15.)

    def test_the_length_of_the_recording_is_shown(self):
        widget, source = self.withSource()
        widget.nframes.setValue(50)
        widget.record()
        self.assertEqual(widget.positionLabel.text(), 'frame 0 / 50')

    def test_record_when_recording_stops(self):
        widget, source = self.withSource()
        widget.record()
        widget.record()
        self.assertFalse(widget.isRecording())

    def test_the_time_recorded_follows_the_rate_of_the_recording(self):
        widget, source = self.withSource()
        widget.nskip.setValue(2)
        widget.record()
        widget._setFrameNumber(15)  # 15 frames at 15 frames/s
        self.assertTrue(widget.timeLabel.text().startswith('0:01.0'))

    def test_the_recorded_frames_are_shown(self):
        widget, source = self.withSource()
        widget.record()
        widget._setFrameNumber(7)
        self.assertEqual(widget.framenumber, 7)
        self.assertIn('7', widget.positionLabel.text())

    def test_a_frame_count_after_the_recording_is_ignored(self):
        widget, source = self.withSource()
        widget.record()
        widget.stop()
        widget._setFrameNumber(5)  # queued before stop, delivered after
        self.assertEqual(widget.framenumber, 0)

    def test_counts_from_the_recorder_are_shown(self):
        widget, source = self.withSource()
        widget.nframes.setValue(50)
        widget.record()
        widget.recorder.frameNumber.emit(12)
        self.assertEqual(widget.positionLabel.text(), 'frame 12 / 50')

    def test_the_recorder_ending_clears_the_display(self):
        widget, source = self.withSource()
        widget.record()
        widget._setFrameNumber(7)
        widget.recorder.stop()  # as when the writer has all its frames
        self.assertEqual(widget.framenumber, 0)
        self.assertTrue(widget.recordButton.isEnabled())
        self.assertFalse(widget.stopButton.isEnabled())

    def test_the_signals_of_the_recorder_are_forwarded(self):
        widget = self.make()
        fractions, lags = record(widget.backlog), record(widget.behind)
        reasons = record(widget.stopped)
        widget.recorder.backlog.emit(0.5)
        widget.recorder.behind.emit(2.)
        widget.recorder.stopped.emit('too slow')
        self.assertEqual((fractions, lags, reasons),
                         ([(0.5,)], [(2.,)], [('too slow',)]))


class TestQDVRWidgetPlay(FileCase):

    def play(self, widget):
        widget.play()
        self.assertTrue(until(widget.isPlaying))

    def test_play_does_nothing_while_recording(self):
        widget, source = self.withSource()
        widget.record()
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
            widget.play()
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
        self.assertEqual(widget.slider.maximum(), 1000)
        self.assertIn('/ 1000', widget.positionLabel.text())

    def test_play_emits_playing_true(self):
        widget = self.widget()
        spy = record(widget.playing)
        self.play(widget)
        self.assertEqual(spy, [(True,)])

    def test_the_frames_of_the_video_are_emitted(self):
        widget = self.widget()
        frames = record(widget.newFrame)
        self.play(widget)
        self.assertTrue(until(lambda: len(frames) > 2))

    def test_play_resumes_if_paused(self):
        widget = self.widget()
        self.play(widget)
        widget.pause()
        self.assertTrue(widget.isPaused())
        widget.play()
        self.assertFalse(widget.isPaused())

    def test_play_does_nothing_if_already_playing(self):
        widget = self.widget()
        self.play(widget)
        first = widget.playback.source
        widget.play()
        self.assertIs(widget.playback.source, first)

    def test_play_does_not_start_if_the_file_will_not_open(self):
        widget = self.widget()
        with patch.object(FakeReader, 'opens', False):
            with self.assertLogs('QVideo.lib.QVideoReader', 'WARNING'):
                widget.play()
        self.assertFalse(widget.isPlaying())

    def test_the_end_of_the_video_pauses_and_shows_play(self):
        widget = self.widget()
        with patch.object(FakeReader, 'LENGTH', 20):
            self.play(widget)
            self.assertTrue(until(widget.isPaused))
        self.assertEqual(widget.playButton.toolTip(), 'Play')
        self.assertEqual(widget.framenumber, 20)

    def test_play_restarts_a_video_that_has_ended(self):
        widget = self.widget()
        slow = patch.object(FakeReader, 'fps', new_callable=PropertyMock,
                            return_value=40.)
        with patch.object(FakeReader, 'LENGTH', 20), slow:
            self.play(widget)
            self.assertTrue(until(widget.isPaused))
            widget.play()
            self.assertFalse(widget.isPaused())
            self.assertTrue(until(lambda: widget.framenumber < 20))


class TestQDVRWidgetRecordChecks(FileCase):

    def widget(self, create=True):
        widget = super().widget(create)
        widget.source = MockSource()
        return widget

    def test_a_new_file_is_recorded_without_asking(self):
        widget = self.widget(create=False)
        widget.record()
        self.assertTrue(widget.isRecording())

    def test_an_existing_file_is_replaced_if_the_user_agrees(self):
        widget = self.widget()
        Yes = QtWidgets.QMessageBox.StandardButton.Yes
        with patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=Yes) as question:
            widget.record()
        question.assert_called_once()
        self.assertTrue(widget.isRecording())

    def test_an_existing_file_is_kept_if_the_user_declines(self):
        widget = self.widget()
        No = QtWidgets.QMessageBox.StandardButton.No
        with patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=No):
            widget.record()
        self.assertFalse(widget.isRecording())

    def test_the_default_answer_is_to_keep_the_file(self):
        widget = self.widget()
        No = QtWidgets.QMessageBox.StandardButton.No
        with patch.object(QtWidgets.QMessageBox, 'question',
                          return_value=No) as question:
            widget.record()
        self.assertEqual(question.call_args.args[-1], No)

    def test_a_read_only_file_is_not_recorded_over(self):
        widget = self.widget()
        with patch('os.access', return_value=False), \
                patch.object(QtWidgets.QMessageBox, 'warning') as warning:
            widget.record()
        self.assertIn('read-only', warning.call_args.args[2])
        self.assertFalse(widget.isRecording())

    def test_a_folder_that_cannot_be_written_is_reported(self):
        widget = self.widget(create=False)
        with patch('os.access', return_value=False), \
                patch.object(QtWidgets.QMessageBox, 'warning') as warning:
            widget.record()
        self.assertIn(str(self.dir), warning.call_args.args[2])
        self.assertFalse(widget.isRecording())


class TestQDVRWidgetStop(WidgetCase):

    def test_stop_when_idle_is_safe(self):
        self.make().stop()

    def test_stop_resets_framenumber(self):
        widget = self.make()
        widget._display(100, 200, 30.)
        widget._update(False)
        self.assertEqual(widget.framenumber, 0)

    def test_stop_stops_playback(self):
        widget = self.playing()
        widget.stop()
        self.assertFalse(widget.isPlaying())
        self.assertIsNone(widget.playback.source)

    def test_stop_emits_playing_false(self):
        widget = self.playing()
        spy = record(widget.playing)
        widget.stop()
        self.assertEqual(spy, [(False,)])

    def test_stop_clears_the_display(self):
        widget = self.playing()
        widget._display(30, 100, 30.)
        widget.stop()
        self.assertEqual(widget.framenumber, 0)

    def test_stop_stops_recording(self):
        widget, source = self.withSource()
        widget.record()
        widget.stop()
        self.assertFalse(widget.isRecording())

    def test_stop_emits_recording_false(self):
        widget, source = self.withSource()
        widget.record()
        spy = record(widget.recording)
        widget.stop()
        self.assertEqual(spy, [(False,)])

    def test_stop_and_the_stop_button_agree(self):
        widget, source = self.withSource()
        widget.record()
        self.assertTrue(widget.stopButton.isEnabled())
        widget.stopButton.click()
        self.assertFalse(widget.isRecording())


class TestQDVRWidgetPause(WidgetCase):

    def test_pause_pauses_playback(self):
        widget = self.playing()
        self.assertTrue(widget.isPaused())

    def test_pausing_twice_leaves_it_paused(self):
        widget = self.playing()
        widget.pause()
        self.assertTrue(widget.isPaused())

    def test_play_resumes_a_paused_video(self):
        widget = self.playing()
        widget.play()
        self.assertFalse(widget.isPaused())

    def test_pause_does_nothing_when_not_playing(self):
        self.make().pause()  # must not raise


class TestQDVRWidgetRewind(WidgetCase):

    def test_rewind_pauses_on_the_first_frame(self):
        widget = self.playing()
        widget.seek(500)
        self.assertTrue(until(lambda: widget.framenumber >= 500))
        widget.rewind()
        self.assertTrue(until(lambda: widget.framenumber == 1))
        self.assertTrue(widget.isPaused())

    def test_rewind_does_nothing_when_not_playing(self):
        self.make().rewind()  # must not raise


class TestQDVRWidgetSeek(WidgetCase):

    def test_step_forward_shows_the_next_frame(self):
        widget = self.playing()
        widget.seek(9)
        self.assertTrue(until(lambda: widget.framenumber == 10))
        widget.step(1)
        self.assertTrue(until(lambda: widget.framenumber == 11))

    def test_step_back_shows_the_previous_frame(self):
        widget = self.playing()
        widget.seek(9)
        self.assertTrue(until(lambda: widget.framenumber == 10))
        widget.step(-1)
        self.assertTrue(until(lambda: widget.framenumber == 9))

    def test_stepping_pauses(self):
        widget = self.playing()
        widget.play()
        widget.step(1)
        self.assertTrue(widget.isPaused())

    def test_seek_does_not_pause(self):
        widget = self.playing()
        widget.play()
        widget.seek(20)
        self.assertFalse(widget.isPaused())

    def test_seek_when_not_playing_is_ignored(self):
        self.make().seek(3)  # must not raise

    def test_moving_the_slider_seeks(self):
        widget = self.playing()
        with patch.object(widget.playback, 'seek') as seek:
            widget.slider.setValue(40)
        seek.assert_called_once_with(39)

    def test_showing_a_frame_does_not_seek(self):
        widget = self.playing()
        with patch.object(widget.playback, 'seek') as seek:
            widget._display(50, 100, 30.)
        seek.assert_not_called()


class TestQDVRWidgetFollow(WidgetCase):

    def test_the_display_follows_the_player(self):
        widget = self.playing(length=100)
        widget.playback.positionChanged.emit(25)
        self.assertEqual(widget.framenumber, 25)
        self.assertEqual(widget.positionLabel.text(), 'frame 25 / 100')
        self.assertEqual(widget.timeLabel.text(), '0:00.1 / 0:00.5')

    def test_a_video_of_unknown_length_grows_the_slider(self):
        widget = self.playing()
        with patch.object(QPlayer, 'length', new_callable=PropertyMock,
                          return_value=0):
            widget._follow(5)
        self.assertEqual(widget.slider.maximum(), 5)


class TestQDVRWidgetControls(WidgetCase):

    def test_idle_without_a_source_only_play_is_available(self):
        widget = self.make()
        for button in (widget.recordButton, widget.stopButton,
                       widget.rewindButton, widget.backButton,
                       widget.forwardButton):
            self.assertFalse(button.isEnabled())
        self.assertTrue(widget.playButton.isEnabled())

    def test_the_slider_is_drawn_but_inert_when_idle(self):
        slider = self.make().slider
        Attribute = QtCore.Qt.WidgetAttribute
        self.assertTrue(slider.isEnabled())
        self.assertGreater(slider.maximum(), slider.minimum())
        self.assertTrue(slider.testAttribute(
            Attribute.WA_TransparentForMouseEvents))
        self.assertEqual(slider.focusPolicy(), QtCore.Qt.FocusPolicy.NoFocus)

    def test_the_slider_responds_while_playing(self):
        widget = self.playing()
        self.assertFalse(widget.slider.testAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents))

    def test_the_slider_keeps_a_range_after_stopping(self):
        widget = self.playing()
        widget.stop()
        self.assertGreater(widget.slider.maximum(), 0)

    def test_recording_allows_only_stop(self):
        widget, source = self.withSource()
        widget.record()
        self.assertTrue(widget.stopButton.isEnabled())
        self.assertFalse(widget.playButton.isEnabled())

    def test_playing_enables_the_transport_controls(self):
        widget, source = self.withSource()
        widget.playback.start('test.avi')
        for control in (widget.rewindButton, widget.backButton,
                        widget.forwardButton, widget.slider,
                        widget.stopButton):
            self.assertTrue(control.isEnabled())
        self.assertFalse(widget.recordButton.isEnabled())

    def test_the_play_button_shows_pause_while_playing(self):
        widget = self.playing()
        widget.play()
        self.assertEqual(widget.playButton.toolTip(), 'Pause')
        widget.pause()
        self.assertEqual(widget.playButton.toolTip(), 'Play')

    def test_the_play_button_pauses_then_resumes(self):
        widget = self.playing()
        widget.play()
        widget.playButton.click()
        self.assertTrue(widget.isPaused())
        widget.playButton.click()
        self.assertFalse(widget.isPaused())

    def test_stopping_restores_the_play_button(self):
        widget = self.playing()
        widget.play()
        widget.stop()
        self.assertEqual(widget.playButton.toolTip(), 'Play')

    def test_the_clock(self):
        self.assertEqual(_clock(0), '0:00.0')
        self.assertEqual(_clock(65.4), '1:05.4')


class TestQDVRWidgetIcons(WidgetCase):

    def test_the_icons_have_the_color_of_the_button_text(self):
        widget = self.make()
        text = widget.palette().buttonText().color()
        image = widget.stopButton.icon().pixmap(24, 24).toImage()
        colors = {QtGui.QColor(image.pixel(x, y)).rgb()
                  for x in range(image.width()) for y in range(image.height())
                  if QtGui.QColor.fromRgba(image.pixel(x, y)).alpha() == 255}
        self.assertEqual(colors, {text.rgb()})

    def test_the_icons_follow_a_dark_palette(self):
        widget = self.make()
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
        self.assertEqual(self.make().recordButton.text(), '')

    def test_the_record_button_falls_back_to_text_without_svg_support(self):
        module = sys.modules['QVideo.dvr.QDVRWidget']
        with patch.object(module, '_record', return_value=QtGui.QIcon()):
            widget = self.make()
        self.assertEqual(widget.recordButton.text(), 'Record')


class TestQDVRWidgetGetFileName(WidgetCase):

    def test_returns_empty_when_playing(self):
        self.assertEqual(self.playing().getFileName(), '')

    def test_returns_empty_when_recording(self):
        widget, source = self.withSource()
        widget.record()
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
        _, dialog = self.choose(self.make(), 'a.avi')
        Dialog = QtWidgets.QFileDialog
        self.assertEqual(dialog.labelText(Dialog.DialogLabel.Accept),
                         'Select')
        self.assertEqual(dialog.acceptMode(), Dialog.AcceptMode.AcceptSave)

    def test_does_not_ask_before_replacing_a_file(self):
        _, dialog = self.choose(self.make(), 'a.avi')
        Option = QtWidgets.QFileDialog.Option
        self.assertTrue(dialog.testOption(Option.DontConfirmOverwrite))

    def test_sets_the_filename(self):
        widget = self.make()
        result, _ = self.choose(widget, 'chosen.avi')
        self.assertEqual(result, 'chosen.avi')
        self.assertEqual(widget.filename, 'chosen.avi')

    def test_keeps_the_filename_when_cancelled(self):
        widget = self.make(filename='original.avi')
        result, _ = self.choose(widget)
        self.assertEqual(result, '')
        self.assertEqual(widget.filename, 'original.avi')


class TestQDVRWidgetNoFilename(WidgetCase):

    def test_record_does_nothing_without_filename(self):
        widget, source = self.withSource()
        widget.fileEdit.setText('')
        with patch.object(widget, 'getFileName', return_value=''):
            widget.record()
        self.assertFalse(widget.isRecording())

    def test_play_does_nothing_without_filename(self):
        widget = self.make()
        widget.fileEdit.setText('')
        with patch.object(widget, 'getFileName', return_value=''):
            widget.play()
        self.assertFalse(widget.isPlaying())


class TestQDVRWidgetCloseEvent(WidgetCase):

    def test_close_event_calls_stop(self):
        widget = self.make()
        with patch.object(widget, 'stop') as mock_stop:
            widget.closeEvent(QtGui.QCloseEvent())
        mock_stop.assert_called_once()

    def test_closing_ends_a_recording_and_a_video(self):
        widget, source = self.withSource()
        widget.record()
        widget.close()
        self.assertFalse(widget.isRecording())
        widget = self.playing()
        widget.close()
        self.assertFalse(widget.isPlaying())


if __name__ == '__main__':
    unittest.main()
