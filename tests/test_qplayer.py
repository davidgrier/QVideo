'''Unit tests for QPlayer.'''
import unittest
from unittest.mock import patch, PropertyMock
from qtpy import QtWidgets
from QVideo.dvr import QPlayer, formats
from QVideo.tests.fakes import FakeReader, until
from QVideo.tests.signals import record


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class PlayerCase(unittest.TestCase):

    def setUp(self):
        patcher = patch.dict(formats.Reader, {'.fake': FakeReader})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.player = QPlayer()
        self.addCleanup(self.player.stop)


class TestStart(PlayerCase):

    def test_it_is_not_playing_at_first(self):
        self.assertFalse(self.player.isPlaying())
        self.assertIsNone(self.player.source)

    def test_starting_plays_the_video(self):
        on = record(self.player.playing)
        self.player.start('x.fake')
        self.assertTrue(self.player.isPlaying())
        self.assertEqual(on, [(True,)])

    def test_the_length_and_rate_are_those_of_the_video(self):
        self.player.start('x.fake')
        self.assertEqual((self.player.length, self.player.fps), (10, 200.))

    def test_an_unsupported_extension_is_an_error(self):
        with self.assertRaises(ValueError):
            self.player.start('x.xyz')
        self.assertFalse(self.player.isPlaying())

    def test_a_file_that_will_not_open_is_an_error(self):
        with patch.object(FakeReader, 'opens', False):
            with self.assertLogs('QVideo.lib.QVideoReader', 'WARNING'):
                with self.assertRaises(OSError):
                    self.player.start('x.fake')
        self.assertFalse(self.player.isPlaying())

    def test_starting_again_replaces_the_video(self):
        self.player.start('x.fake')
        first = self.player.source
        self.player.start('y.fake')
        self.assertIsNot(self.player.source, first)
        self.assertFalse(first.isRunning())


class TestPlaying(PlayerCase):

    def test_the_frames_are_played_in_order(self):
        frames = record(self.player.newFrame)
        self.player.start('x.fake')
        self.assertTrue(until(lambda: len(frames) == 10))
        self.assertEqual([int(f[0][0, 0]) for f in frames], list(range(10)))

    def test_it_pauses_at_the_end_and_says_so(self):
        ended = record(self.player.ended)
        self.player.start('x.fake')
        self.assertTrue(until(lambda: self.player.framenumber == 10))
        self.assertTrue(until(lambda: len(ended) == 1))
        self.assertTrue(self.player.isPaused())
        self.assertTrue(self.player.isPlaying())

    def test_the_position_is_reported(self):
        positions = record(self.player.positionChanged)
        self.player.start('x.fake')
        self.assertTrue(until(lambda: self.player.framenumber == 10))
        self.assertEqual(positions[0], (0,))
        self.assertEqual(positions[-1], (10,))

    def test_resuming_after_the_end_starts_again(self):
        slow = patch.object(FakeReader, 'fps', new_callable=PropertyMock,
                            return_value=40.)
        with slow:
            self.player.start('x.fake')
            self.assertTrue(until(lambda: self.player.framenumber == 10))
            self.assertTrue(until(self.player.isPaused))
            self.player.resume()
            self.assertFalse(self.player.isPaused())
            self.assertTrue(until(lambda: self.player.framenumber < 10))


class TestControl(PlayerCase):

    def setUp(self):
        super().setUp()
        self.player.start('x.fake')
        self.assertTrue(until(self.player.isPaused))

    def test_pause_and_resume(self):
        self.player.seek(2)
        self.player.resume()
        self.assertFalse(self.player.isPaused())
        self.player.pause()
        self.assertTrue(self.player.isPaused())

    def test_seek_goes_to_that_frame(self):
        frames = record(self.player.newFrame)
        self.player.seek(4)  # frames of the first playback may still arrive
        self.assertTrue(until(
            lambda: any(int(f[0][0, 0]) == 4 for f in frames)))

    def test_seek_is_kept_inside_the_video(self):
        self.player.seek(500)
        self.assertTrue(until(lambda: self.player.framenumber == 10))
        self.player.seek(-5)
        self.assertTrue(until(lambda: self.player.framenumber == 1))

    def test_rewind_pauses_on_the_first_frame(self):
        self.player.rewind()
        self.assertTrue(until(lambda: self.player.framenumber == 1))
        self.assertTrue(self.player.isPaused())

    def test_step_moves_one_frame(self):
        self.player.rewind()
        self.assertTrue(until(lambda: self.player.framenumber == 1))
        self.player.step()
        self.assertTrue(until(lambda: self.player.framenumber == 2))
        self.player.step(-1)
        self.assertTrue(until(lambda: self.player.framenumber == 1))
        self.assertTrue(self.player.isPaused())

    def test_controls_without_a_video_do_nothing(self):
        player = QPlayer()
        player.pause()
        player.resume()
        player.seek(3)
        player.rewind()
        player.step()
        self.assertFalse(player.isPlaying())
        self.assertFalse(player.isPaused())


class TestStop(PlayerCase):

    def test_stopping_ends_playback(self):
        on = record(self.player.playing)
        self.player.start('x.fake')
        source = self.player.source
        self.player.stop()
        self.assertFalse(self.player.isPlaying())
        self.assertFalse(source.isRunning())
        self.assertEqual(on, [(True,), (False,)])

    def test_stopping_twice_is_safe(self):
        off = record(self.player.playing)
        self.player.start('x.fake')
        self.player.stop()
        self.player.stop()
        self.assertEqual(off, [(True,), (False,)])

    def test_stopping_without_a_video_is_safe(self):
        self.player.stop()

    def test_stopping_is_safe_when_signals_are_already_disconnected(self):
        self.player.start('x.fake')
        self.player.source.newFrame.disconnect(self.player._follow)
        self.player.stop()
        self.assertFalse(self.player.isPlaying())

    def test_a_frame_that_arrives_after_stopping_is_harmless(self):
        self.player._follow()


if __name__ == '__main__':
    unittest.main()
