# -*- coding: utf-8 -*-

from PyQt5 import uic
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, pyqtProperty,
                          QObject, QThread)
from PyQt5.QtWidgets import (QFrame, QFileDialog)
from pathlib import Path
from typing import Optional
from QVideo.lib import (clickable, QVideoSource)
from .QAVIWriter import QAVIWriter
from .QAVISource import QAVISource
from .icons_rc import *
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QDVRWidget(QFrame):
    '''GUI for a Digital Video Recorder (DVR)

    Inherits
    --------
    PyQt5.QtWidgets.QFrame

    Properties
    ----------
    source: QVideoSource
        Source of video frames to present and record

    filename: str
        Name of video file to save and record

    Methods
    -------
    All methods are invoked by widgets described in QDVRWidget.ui
    '''

    recording = pyqtSignal(bool)
    playing = pyqtSignal(bool)

    def __init__(self,
                 *args,
                 source: Optional[QVideoSource] = None,
                 filename: Optional[str] = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        dir = Path(__file__).parent
        uic.loadUi(dir / 'QDVRWidget.ui', self)
        self._writer = None
        self._player = None
        self._framenumber = 0
        self.connectSignals()
        self.source = source
        self.filename = filename or str(Path.home() / 'default.avi')

    def connectSignals(self) -> None:
        '''Connect signals to slots for user interaction'''
        clickable(self.playEdit).connect(lambda: self.getFileName(False))
        clickable(self.saveEdit).connect(lambda: self.getFileName(True))
        self.recordButton.clicked.connect(self.record)
        self.stopButton.clicked.connect(self.stop)
        self.rewindButton.clicked.connect(self.rewind)
        self.pauseButton.clicked.connect(self.pause)
        self.playButton.clicked.connect(self.play)

    def isRecording(self) -> bool:
        '''Return True if recording in progress'''
        return (self._writer is not None)

    def isPlaying(self) -> bool:
        '''Return True is video is playing'''
        return (self._player is not None)

    def isPaused(self) -> bool:
        '''Return True if video playback is paused'''
        if self.isPlaying():
            return self._player.isPaused()
        return False

    def getFileName(self, save: bool = False) -> str:
        if self.isRecording():
            return
        if save:
            get = QFileDialog.getSaveFileName
        else:
            get = QFileDialog.getOpenFileName
        filename, _ = get(self, 'Video File Name',
                          str(self.filename),
                          'Video files (*.avi)')
        if filename:
            self.playname = filename
            if save:
                self.filename = filename
        return filename

    @pyqtSlot()
    def record(self) -> None:
        '''Implement functionality of Record button'''
        if self.isPlaying():
            return
        if self.isRecording():
            self.stop()
            return
        if self.source is None:
            return
        if not (self.filename or self.getFileName(save=True)):
            return
        logger.debug(f'Recording: {self.filename}')
        suffix = Path(self.filename).suffix
        if suffix == '.avi':
            self._writer = QAVIWriter(self.filename,
                                      fps=self.source.fps,
                                      nframes=self.nframes.value(),
                                      nskip=self.nskip.value())
        else:
            logger.debug(f'unsupported file extension {suffix}')
            return
        self._writer.frameNumber.connect(self.setFrameNumber)
        self._writer.finished.connect(self.stop)
        self._thread = QThread()
        self._thread.finished.connect(self._writer.close)
        self._writer.moveToThread(self._thread)
        self._thread.start()
        self.source.newFrame.connect(self._writer.write)
        self.recording.emit(True)

    @pyqtSlot()
    def play(self) -> None:
        '''Implement functionality of Play buttoon'''
        if self.isPaused():
            self._player.resume()
            return
        if self.isRecording() or self.isPlaying():
            return
        if not (self.playname or self.getFilename(save=False)):
            return
        self.framenumber = 0
        logger.debug(f'Starting Playback: {self.playname}')
        suffix = Path(self.playname).suffix
        if suffix == '.avi':
            self._player = QAVISource(self.playname)
        else:
            logger.debug(f'unsupported file extension {suffix}')
            return
        if self._player.isOpen():
            logger.debug('connecting signals')
            self.newFrame = self._player.newFrame
            self.newFrame.connect(self.stepFrameNumber)
            self.playing.emit(True)
            self._player.start()
        else:
            self._player = None

    @pyqtSlot()
    def pause(self) -> None:
        '''Implement functionality of Pause button'''
        if self.isPlaying():
            if self._player.isPaused():
                self._player.resume()
            else:
                self._player.pause()

    @pyqtSlot()
    def rewind(self) -> None:
        '''Implement functionality of Rewind button'''
        if self.isPlaying():
            self._player.source.rewind()
            self._player.pause()
            self.framenumber = 0

    @pyqtSlot()
    def stop(self) -> None:
        '''Implement functionality of Stop button'''
        if self.isRecording():
            logger.debug('Stopping Recording')
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._writer = None
            self.recording.emit(False)
        if self.isPlaying():
            logger.debug('Stopping Playback')
            self.newFrame.disconnect()
            self._player.stop()
            self._player = None
            self.playing.emit(False)
        self.framenumber = 0

    @pyqtSlot(int)
    def setFrameNumber(self, framenumber: int) -> None:
        '''Set frame number'''
        self.framenumber = framenumber

    @pyqtSlot()
    def stepFrameNumber(self) -> None:
        '''Increment frame number'''
        self.framenumber += 1

    @pyqtProperty(QObject)
    def source(self) -> QObject:
        return self._source

    @source.setter
    def source(self, source) -> None:
        self._source = source
        self.recordButton.setDisabled(source is None)

    @pyqtProperty(str)
    def filename(self) -> str:
        '''Current file name from Save widget'''
        return str(self.saveEdit.text())

    @filename.setter
    def filename(self, filename: str) -> None:
        if filename is None:
            return
        if not (self.isRecording() or self.isPlaying()):
            self.saveEdit.setText(filename)
            self.playname = self.filename

    @pyqtProperty(str)
    def playname(self) -> str:
        '''Current filename from Play widget'''
        return str(self.playEdit.text())

    @playname.setter
    def playname(self, filename: str) -> None:
        if not (self.isPlaying()):
            self.playEdit.setText(filename)

    @pyqtProperty(int)
    def framenumber(self) -> int:
        '''Current frame number'''
        return self._framenumber

    @framenumber.setter
    def framenumber(self, number: int) -> None:
        self._framenumber = number
        self.frameNumber.display(self._framenumber)
