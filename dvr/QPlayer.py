'''Headless player: plays a video file at its own frame rate.'''
import logging
import numpy as np
from qtpy import QtCore
from QVideo.lib import QVideoSource
from . import formats


__all__ = ['QPlayer']


logger = logging.getLogger(__name__)


class QPlayer(QtCore.QObject):

    '''Plays a video file at its own frame rate, without a window.

    The frames are read on a thread of their own by a
    :class:`~QVideo.lib.QVideoSource.QVideoSource`, so
    :attr:`source` can be given to a screen, a filter pipeline or anything
    else that takes the frames of a source.  The class that reads the file
    is the one that :mod:`~QVideo.dvr.formats` has for its extension.  When
    the video reaches its end the player pauses on the last frame and emits
    :attr:`ended`; :meth:`resume` then starts it again from the beginning.

    To get the frames of a recording as arrays, for analysis, use
    :func:`~QVideo.dvr.formats.openVideo` instead: the reader that it
    returns can be indexed and iterated, and nothing waits for a clock.

    The player is a Qt object like any other: its signals reach it through
    the event loop of the application, which must be running.  Without one,
    the video is read but not followed, so it does not pause at its end.

    Signals
    -------
    newFrame(Image, FrameInfo)
        Emitted for each frame that is played.
    playing(bool)
        Emitted when playback starts (``True``) or stops (``False``).
    positionChanged(int)
        Emitted with the number of frames that have been played, which is
        the index, plus one, of the frame that is shown.
    ended()
        Emitted when the video has been played to its end.

    Examples
    --------
    Play a video through a filter pipeline::

        player = QPlayer()
        player.start('run.mkv')
        screen.source = player.source

    Play a video in a script, and quit when it ends::

        app = QCoreApplication([])
        player = QPlayer()
        player.ended.connect(app.quit)
        player.start('run.mkv')
        app.exec()
    '''

    #: Emitted for each frame that is played.
    newFrame = QtCore.Signal(np.ndarray, object)
    #: Emitted when playback starts (``True``) or stops (``False``).
    playing = QtCore.Signal(bool)
    #: Emitted with the number of frames that have been played.
    positionChanged = QtCore.Signal(int)
    #: Emitted when the video has been played to its end.
    ended = QtCore.Signal()

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._source: QVideoSource | None = None
        self._length = 0
        self._fps = 1.
        self._position = 0
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    @property
    def source(self) -> QVideoSource | None:
        '''The source of the frames, or ``None`` when not playing.'''
        return self._source

    @property
    def length(self) -> int:
        '''Number of frames in the video (0 if the file does not say).'''
        return self._length

    @property
    def fps(self) -> float:
        '''Frame rate of the video [frames per second].'''
        return self._fps

    @property
    def framenumber(self) -> int:
        '''Number of frames that have been played.'''
        return self._position

    def isPlaying(self) -> bool:
        '''Return ``True`` if a video is open, whether paused or not.'''
        return self._source is not None

    def isPaused(self) -> bool:
        '''Return ``True`` if playback is paused.'''
        return self.isPlaying() and self._source.isPaused()

    def start(self, filename: str) -> None:
        '''Open *filename* and start to play it from the beginning.

        A video that is playing is stopped first.

        Raises
        ------
        ValueError
            If the extension of *filename* is not supported.
        OSError
            If the file cannot be opened.
        '''
        self.stop()
        reader = formats.readerClass(filename)(filename)
        if not reader.isOpen():
            raise OSError(f'cannot open {filename!r} for playing')
        logger.debug(f'Starting playback: {filename}')
        # Ask the reader before its thread runs: it is not safe to ask
        # while it reads.
        self._length, self._fps = reader.length, reader.fps
        self._position = 0
        self._source = QVideoSource(reader)
        self._source.newFrame.connect(self._follow)
        self._source.newFrame.connect(self.newFrame)
        self.playing.emit(True)
        self.positionChanged.emit(0)
        self._source.start()

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop playing and close the file.

        It does nothing if no video is open, so it may be called again,
        and it is called when the application is about to quit.
        '''
        if not self.isPlaying():
            return
        logger.debug('Stopping playback')
        source = self._source
        try:
            source.newFrame.disconnect(self._follow)
            source.newFrame.disconnect(self.newFrame)
        except (RuntimeError, TypeError):
            logger.debug('Playback signals were already disconnected')
        source.stop()
        source.wait()
        self._source = None
        self.playing.emit(False)

    def pause(self) -> None:
        '''Pause playback.  :meth:`resume` continues it.'''
        if self.isPlaying():
            self._source.pause()

    def resume(self) -> None:
        '''Continue after a pause, from the start if the video had ended.'''
        if not self.isPlaying():
            return
        if self.isPaused() and 0 < self._length <= self._position:
            self._source.seek(0)
        self._source.resume()

    @QtCore.Slot(int)
    def seek(self, framenumber: int) -> None:
        '''Go to frame *framenumber* (zero-based) of the video.

        The video keeps playing, or stays paused, as it was.  A frame
        outside the video is replaced by the nearest one inside it.
        '''
        if self.isPlaying():
            framenumber = max(framenumber, 0)
            if self._length:
                framenumber = min(framenumber, self._length - 1)
            self._source.seek(framenumber)

    def rewind(self) -> None:
        '''Go to the first frame and pause.'''
        self._pauseAt(0)

    def step(self, frames: int = 1) -> None:
        '''Pause and move *frames* frames forward, or back if negative.'''
        self._pauseAt(self._position - 1 + frames)

    def _pauseAt(self, framenumber: int) -> None:
        self.pause()
        self.seek(framenumber)

    def _follow(self) -> None:
        '''Report where playback is; pause at the end of the video.'''
        if not self.isPlaying():  # a frame that arrives after stopping
            return
        done = self._source.source.framenumber
        self._position = done
        self.positionChanged.emit(done)
        if 0 < self._length <= done and not self.isPaused():
            self._source.pause()
            self.ended.emit()
